from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.jira_analytics.allocation.role_mapping import DIRECT_PRODUCTION_ROLES
from app.jira_analytics.allocation.topic_classifier import classify_topic_type
from app.jira_analytics.project_scope import (
    allowed_issue_ids_subquery,
    apply_feature_root_scope,
    apply_issue_scope,
    apply_worklog_issue_scope,
)
from app.jira_analytics.models import (
    AllocationRoleRule,
    JiraFeatureMembership,
    JiraFeatureRoot,
    JiraIssue,
    JiraIssueDetail,
    JiraUser,
    JiraUserMonthlyHrworksHours,
    JiraUserRoleAssignment,
    JiraWorklog,
    MonthlyAllocatedEffort,
    MonthlyTopicEffortBase,
)
from app.jira_analytics.allocation.effective_rule import effective_allocation_params


def _month_start(dt: datetime) -> date:
    d = dt.date() if isinstance(dt, datetime) else dt
    return date(d.year, d.month, 1)


def _hours(seconds: int) -> Decimal:
    return Decimal(seconds) / Decimal(3600)


def rebuild_monthly_allocation(
    db: Session,
    *,
    settings_json: dict | None = None,
    period_months: list[date] | None = None,
) -> dict[str, Any]:
    del settings_json
    if period_months is None:
        period_months = _distinct_worklog_months(db)
    if not period_months:
        return {"periods": [], "topic_rows": 0, "allocation_rows": 0}
    total_topic = 0
    total_alloc = 0
    rules = _load_role_rules(db)
    assignments_by_account = _assignment_rows_by_account(db)
    excluded_accounts = _reporting_excluded_accounts(db)
    for period in period_months:
        db.execute(delete(MonthlyTopicEffortBase).where(MonthlyTopicEffortBase.period_month == period))
        db.execute(delete(MonthlyAllocatedEffort).where(MonthlyAllocatedEffort.period_month == period))
        topic_rows = _refresh_topic_base(db, period, assignments_by_account, excluded_accounts)
        alloc_rows = _allocate_period(db, period, rules, assignments_by_account)
        total_topic += topic_rows
        total_alloc += alloc_rows
    db.commit()
    return {
        "periods": [p.isoformat() for p in period_months],
        "topic_rows": total_topic,
        "allocation_rows": total_alloc,
    }


def _distinct_worklog_months(db: Session) -> list[date]:
    rows = db.execute(
        apply_worklog_issue_scope(
            select(JiraWorklog.started_at).where(JiraWorklog.started_at.is_not(None)).distinct()
        )
    ).scalars().all()
    months: set[date] = set()
    for started in rows:
        if started is None:
            continue
        months.add(_month_start(started))
    return sorted(months)


def _load_role_rules(db: Session) -> dict[str, AllocationRoleRule]:
    rows = db.execute(select(AllocationRoleRule).where(AllocationRoleRule.active.is_(True))).scalars().all()
    return {r.role_name: r for r in rows}


def _assignment_rows_by_account(db: Session) -> dict[str, list[JiraUserRoleAssignment]]:
    rows = db.execute(
        select(JiraUserRoleAssignment)
        .where(JiraUserRoleAssignment.user_account_id.is_not(None))
        .where(JiraUserRoleAssignment.active.is_(True))
        .order_by(JiraUserRoleAssignment.user_account_id.asc(), JiraUserRoleAssignment.valid_from.asc())
    ).scalars().all()
    by_account: dict[str, list[JiraUserRoleAssignment]] = defaultdict(list)
    for row in rows:
        if row.user_account_id:
            by_account[row.user_account_id].append(row)
    return by_account


def _reporting_excluded_accounts(db: Session) -> frozenset[str]:
    rows = db.execute(
        select(JiraUser.account_id)
        .where(JiraUser.account_id.is_not(None))
        .where(JiraUser.reporting_excluded.is_(True))
    ).scalars().all()
    return frozenset(row for row in rows if row)


def _role_for_worklog(
    *,
    account_id: str | None,
    work_date: date,
    assignments_by_account: dict[str, list[JiraUserRoleAssignment]],
    excluded_accounts: frozenset[str],
) -> str | None:
    if not account_id:
        return None
    if account_id in excluded_accounts:
        return None
    assignment = _assignment_for_user(
        db=None,
        account_id=account_id,
        period=work_date,
        assignments_by_account=assignments_by_account,
    )
    return assignment.role_name if assignment is not None else None


def _refresh_topic_base(
    db: Session,
    period: date,
    assignments_by_account: dict[str, list[JiraUserRoleAssignment]],
    excluded_accounts: frozenset[str],
) -> int:
    month_end = _next_month_start(period)
    wl_rows = db.execute(
        apply_issue_scope(
            select(
                JiraWorklog.issue_id,
                JiraWorklog.author_user_id,
                JiraWorklog.author_account_id,
                JiraWorklog.author_display_name,
                JiraWorklog.started_at,
                JiraWorklog.time_spent_seconds,
                JiraIssue.key,
                JiraIssue.issue_type_name,
                JiraIssue.summary,
                JiraIssueDetail.team_id,
                JiraIssueDetail.team_name,
            )
            .join(JiraIssue, JiraIssue.id == JiraWorklog.issue_id)
            .outerjoin(JiraIssueDetail, JiraIssueDetail.issue_id == JiraIssue.id)
            .where(JiraWorklog.started_at >= period)
            .where(JiraWorklog.started_at < month_end)
        )
    ).all()
    membership = _membership_map(db)
    roots = _feature_root_map(db)
    count = 0
    for row in wl_rows:
        issue_id = row.issue_id
        fm = membership.get(issue_id)
        feature_root_id = fm[0] if fm else None
        feature_key, feature_name = roots.get(feature_root_id, (None, None)) if feature_root_id else (None, None)
        started = row.started_at
        work_date = started.date() if started else period
        role_name = _role_for_worklog(
            account_id=row.author_account_id,
            work_date=work_date,
            assignments_by_account=assignments_by_account,
            excluded_accounts=excluded_accounts,
        )
        if role_name is None or role_name not in DIRECT_PRODUCTION_ROLES:
            continue
        topic_type = classify_topic_type(
            feature_root_id=feature_root_id,
            issue_type_name=row.issue_type_name,
        )
        db.add(
            MonthlyTopicEffortBase(
                period_month=period,
                feature_root_id=feature_root_id,
                feature_key=feature_key,
                feature_name=feature_name,
                issue_id=issue_id,
                issue_key=row.key,
                issue_type_name=row.issue_type_name,
                summary=row.summary,
                team_id=row.team_id,
                team_name=row.team_name,
                user_account_id=row.author_account_id,
                display_name=row.author_display_name,
                role_name=role_name,
                topic_type=topic_type,
                direct_hours=_hours(row.time_spent_seconds),
            )
        )
        count += 1
    db.flush()
    return count


def _topic_key(tr: MonthlyTopicEffortBase) -> tuple:
    return (
        tr.topic_type,
        tr.feature_root_id,
        tr.feature_key,
        tr.feature_name,
        tr.issue_id,
        tr.issue_key,
        tr.team_id,
        tr.team_name,
    )


def _issue_project_map(db: Session, issue_ids: set[int]) -> dict[int, int | None]:
    if not issue_ids:
        return {}
    rows = db.execute(
        select(JiraIssue.id, JiraIssue.project_id).where(JiraIssue.id.in_(issue_ids))
    ).all()
    return {issue_id: project_id for issue_id, project_id in rows}


def _allocate_period(
    db: Session,
    period: date,
    rules: dict[str, AllocationRoleRule],
    assignments_by_account: dict[str, list[JiraUserRoleAssignment]],
) -> int:
    topic_rows = db.execute(
        select(MonthlyTopicEffortBase).where(MonthlyTopicEffortBase.period_month == period)
    ).scalars().all()
    count = 0
    for tr in topic_rows:
        count += 1
        db.add(
            MonthlyAllocatedEffort(
                period_month=period,
                topic_type=tr.topic_type,
                feature_root_id=tr.feature_root_id,
                feature_key=tr.feature_key,
                feature_name=tr.feature_name,
                issue_id=tr.issue_id,
                issue_key=tr.issue_key,
                team_id=tr.team_id,
                team_name=tr.team_name,
                source_user_email=tr.user_account_id or "unknown@local",
                source_display_name=tr.display_name or "Unknown",
                source_role_name=tr.role_name or "Developer",
                allocation_kind="direct_worklog",
                hours=tr.direct_hours,
                allocation_basis_hours=None,
                allocation_percentage=None,
                rule_snapshot_json={"kind": "direct_worklog"},
            )
        )

    issue_ids = {tr.issue_id for tr in topic_rows}
    issue_projects = _issue_project_map(db, issue_ids)

    hr_rows = db.execute(
        select(
            JiraUserMonthlyHrworksHours,
            JiraUser.account_id,
            JiraUser.display_name,
            JiraUser.email_address,
        )
        .join(JiraUser, JiraUser.id == JiraUserMonthlyHrworksHours.jira_user_id)
        .where(JiraUserMonthlyHrworksHours.month_start == period)
        .where(JiraUser.reporting_excluded.is_(False))
    ).all()
    for hr, account_id, display_name, email in hr_rows:
        assignment = _assignment_for_user(
            db,
            account_id,
            period,
            assignments_by_account=assignments_by_account,
        )
        if assignment is None:
            continue
        rule = rules.get(assignment.role_name)
        if rule is None or not rule.is_indirect_role:
            continue
        worked = Decimal(hr.clocked_working_hours)
        overhead_pct, scope, allocatable_pct = effective_allocation_params(rule, assignment)
        overhead_hours = worked * overhead_pct / Decimal(100)
        allocatable = worked * allocatable_pct / Decimal(100)
        if overhead_hours > 0:
            db.add(
                MonthlyAllocatedEffort(
                    period_month=period,
                    topic_type="shared_overhead",
                    feature_root_id=None,
                    feature_key=None,
                    feature_name=None,
                    issue_id=None,
                    issue_key=None,
                    team_id=assignment.team_id,
                    team_name=assignment.team_name,
                    source_user_email=email or f"{account_id}@unknown.local",
                    source_display_name=display_name or "Unknown",
                    source_role_name=assignment.role_name,
                    allocation_kind="shared_overhead",
                    hours=overhead_hours,
                    allocation_basis_hours=worked,
                    allocation_percentage=overhead_pct / Decimal(100),
                    rule_snapshot_json=_snapshot(
                        rule,
                        assignment,
                        worked,
                        overhead_hours,
                        allocatable,
                        scope=scope,
                    ),
                )
            )
            count += 1
        count += _allocate_indirect_project_proportional(
            db,
            period=period,
            topic_rows=topic_rows,
            issue_projects=issue_projects,
            assignment=assignment,
            rule=rule,
            scope=scope,
            allocatable=allocatable,
            account_id=account_id,
            display_name=display_name,
            email=email,
            worked=worked,
            overhead_hours=overhead_hours,
        )
    db.flush()
    return count


def _allocate_indirect_project_proportional(
    db: Session,
    *,
    period: date,
    topic_rows: list[MonthlyTopicEffortBase],
    issue_projects: dict[int, int | None],
    assignment: JiraUserRoleAssignment,
    rule: AllocationRoleRule,
    scope: str,
    allocatable: Decimal,
    account_id: str | None,
    display_name: str | None,
    email: str | None,
    worked: Decimal,
    overhead_hours: Decimal,
) -> int:
    if allocatable <= 0:
        return 0
    team_filter = (assignment.team_name or "").strip().lower() if scope == "team_only" else None
    eligible: list[MonthlyTopicEffortBase] = []
    for tr in topic_rows:
        if team_filter is not None and (tr.team_name or "").strip().lower() != team_filter:
            continue
        eligible.append(tr)
    if not eligible:
        return 0

    project_hours: dict[int | None, Decimal] = defaultdict(lambda: Decimal(0))
    for tr in eligible:
        project_hours[issue_projects.get(tr.issue_id)] += tr.direct_hours
    total_project_hours = sum(project_hours.values())
    if total_project_hours <= 0:
        return 0

    count = 0
    for project_id, proj_hours in project_hours.items():
        project_share = allocatable * (proj_hours / total_project_hours)
        topics_in_project = [
            tr for tr in eligible if issue_projects.get(tr.issue_id) == project_id
        ]
        topic_total = sum(tr.direct_hours for tr in topics_in_project)
        if topic_total <= 0:
            continue
        for tr in topics_in_project:
            topic_alloc = project_share * (tr.direct_hours / topic_total)
            key = _topic_key(tr)
            db.add(
                MonthlyAllocatedEffort(
                    period_month=period,
                    topic_type=tr.topic_type,
                    feature_root_id=tr.feature_root_id,
                    feature_key=tr.feature_key,
                    feature_name=tr.feature_name,
                    issue_id=tr.issue_id,
                    issue_key=tr.issue_key,
                    team_id=tr.team_id,
                    team_name=tr.team_name,
                    source_user_email=email or f"{account_id}@unknown.local",
                    source_display_name=display_name or "Unknown",
                    source_role_name=assignment.role_name,
                    allocation_kind="indirect_allocated",
                    hours=topic_alloc,
                    allocation_basis_hours=total_project_hours,
                    allocation_percentage=tr.direct_hours / topic_total,
                    rule_snapshot_json=_snapshot(
                        rule,
                        assignment,
                        worked,
                        overhead_hours,
                        allocatable,
                        scope=scope,
                        project_id=project_id,
                        project_hours=float(proj_hours),
                        topic_base_hours=float(tr.direct_hours),
                        denominator_hours=float(total_project_hours),
                    ),
                )
            )
            count += 1
    return count


def _assignment_for_user(
    db: Session | None,
    account_id: str | None,
    period: date,
    *,
    assignments_by_account: dict[str, list[JiraUserRoleAssignment]] | None = None,
) -> JiraUserRoleAssignment | None:
    if not account_id:
        return None
    if assignments_by_account is not None:
        rows = assignments_by_account.get(account_id, [])
    else:
        if db is None:
            return None
        rows = db.execute(
            select(JiraUserRoleAssignment)
            .where(JiraUserRoleAssignment.user_account_id == account_id)
            .where(JiraUserRoleAssignment.active.is_(True))
            .order_by(JiraUserRoleAssignment.valid_from.asc())
        ).scalars().all()
    if not rows:
        return None

    for row in reversed(rows):
        if row.valid_from <= period and (row.valid_to is None or row.valid_to >= period):
            return row

    # Initial assignment setup often happens after historical/current-month worklogs
    # already exist. In that case, use the assignment table as the source of truth
    # instead of dropping those worklogs as unassigned.
    previous_rows = [row for row in rows if row.valid_from <= period]
    if previous_rows:
        return previous_rows[-1]
    return rows[0]


def _membership_map(db: Session) -> dict[int, tuple[int, int]]:
    rows = db.execute(
        select(JiraFeatureMembership.member_issue_id, JiraFeatureMembership.feature_root_id).where(
            JiraFeatureMembership.member_issue_id.in_(allowed_issue_ids_subquery())
        )
    ).all()
    return {member_id: (root_id, 0) for member_id, root_id in rows}


def _feature_root_map(db: Session) -> dict[int, tuple[str | None, str | None]]:
    rows = db.execute(
        apply_feature_root_scope(
            select(JiraFeatureRoot.id, JiraFeatureRoot.root_key, JiraFeatureRoot.name)
        )
    ).all()
    return {rid: (key, name) for rid, key, name in rows}


def _next_month_start(period: date) -> date:
    if period.month == 12:
        return date(period.year + 1, 1, 1)
    return date(period.year, period.month + 1, 1)


def _snapshot(
    rule: AllocationRoleRule,
    assignment: JiraUserRoleAssignment,
    worked: Decimal,
    overhead_hours: Decimal,
    allocatable: Decimal,
    *,
    scope: str,
    project_id: int | None = None,
    project_hours: float | None = None,
    topic_base_hours: float | None = None,
    denominator_hours: float | None = None,
) -> dict[str, Any]:
    overhead_pct, _, allocatable_pct = effective_allocation_params(rule, assignment)
    return {
        "role_name": rule.role_name,
        "overhead_percentage": float(overhead_pct),
        "allocatable_percentage": float(allocatable_pct),
        "allocation_scope": scope,
        "hr_worked_hours": float(worked),
        "overhead_hours": float(overhead_hours),
        "allocatable_hours": float(allocatable),
        "project_id": project_id,
        "project_hours": project_hours,
        "topic_base_hours": topic_base_hours,
        "denominator_hours": denominator_hours,
    }
