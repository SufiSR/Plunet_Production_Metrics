from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jira_analytics.models import (
    JiraIssue,
    JiraIssueDetail,
    JiraWorklog,
    MonthlyAllocatedEffort,
    MonthlyTopicEffortBase,
)
from app.jira_analytics.project_scope import (
    apply_issue_scope,
    apply_worklog_issue_scope,
    is_excluded_project_key,
    scope_monthly_allocated_effort,
    scope_monthly_topic_effort,
)
from app.schemas.jira_analytics_reports import (
    AnalyticsReportResponse,
    DrilldownIssueRow,
    DrilldownPeopleWorklogRow,
    DrilldownTopicRow,
)


def _parse_date(value: str | None) -> date | None:
    if not value or not value.strip():
        return None
    return date.fromisoformat(value.strip()[:10])


def drilldown_topics(
    db: Session,
    *,
    period_month: date | None = None,
    topic_type: str | None = None,
    team: str | None = None,
    feature_key: str | None = None,
) -> AnalyticsReportResponse:
    stmt = select(MonthlyTopicEffortBase)
    if period_month:
        stmt = stmt.where(MonthlyTopicEffortBase.period_month == period_month)
    if topic_type:
        stmt = stmt.where(MonthlyTopicEffortBase.topic_type == topic_type)
    if team:
        stmt = stmt.where(MonthlyTopicEffortBase.team_name == team)
    if feature_key:
        stmt = stmt.where(MonthlyTopicEffortBase.feature_key == feature_key)
    rows = db.execute(scope_monthly_topic_effort(stmt)).scalars().all()
    grouped: dict[tuple, Decimal] = {}
    meta: dict[tuple, MonthlyTopicEffortBase] = {}
    for r in rows:
        key = (r.topic_type, r.feature_key, r.feature_name, r.team_name)
        grouped[key] = grouped.get(key, Decimal(0)) + r.direct_hours
        meta[key] = r
    table = [
        DrilldownTopicRow(
            topic_type=k[0],
            feature_key=k[1],
            feature_name=k[2],
            team=k[3],
            direct_hours=float(grouped[k]),
            allocated_hours=0.0,
            total_hours=float(grouped[k]),
        )
        for k in sorted(grouped.keys(), key=lambda x: -float(grouped[x]))
    ]
    return AnalyticsReportResponse(filters={}, table=[r.model_dump() for r in table])


def drilldown_issues(
    db: Session,
    *,
    period_month: date | None = None,
    topic_type: str | None = None,
    feature_key: str | None = None,
    team: str | None = None,
) -> AnalyticsReportResponse:
    stmt = select(
        MonthlyTopicEffortBase,
        JiraIssue.status_name,
    ).join(JiraIssue, JiraIssue.id == MonthlyTopicEffortBase.issue_id)
    if period_month:
        stmt = stmt.where(MonthlyTopicEffortBase.period_month == period_month)
    if topic_type:
        stmt = stmt.where(MonthlyTopicEffortBase.topic_type == topic_type)
    if feature_key:
        stmt = stmt.where(MonthlyTopicEffortBase.feature_key == feature_key)
    if team:
        stmt = stmt.where(MonthlyTopicEffortBase.team_name == team)
    stmt = apply_issue_scope(stmt)
    grouped: dict[str, tuple] = {}
    for base, status in db.execute(stmt).all():
        prev = grouped.get(base.issue_key)
        hours = float(base.direct_hours) + (prev[3] if prev else 0.0)
        grouped[base.issue_key] = (base.summary, base.issue_type_name, status, hours, base.feature_key)
    table = [
        DrilldownIssueRow(
            issue_key=key,
            summary=v[0],
            issue_type=v[1],
            status=v[2],
            team=team,
            feature_root_key=v[4],
            hours=v[3],
            allocation_kind="direct_worklog",
        )
        for key, v in sorted(grouped.items(), key=lambda x: -x[1][3])
    ]
    return AnalyticsReportResponse(filters={}, table=[r.model_dump() for r in table])


def drilldown_people_worklogs(
    db: Session,
    *,
    period_month: date | None = None,
    issue_key: str | None = None,
    feature_key: str | None = None,
) -> AnalyticsReportResponse:
    if issue_key:
        if is_excluded_project_key(issue_key.split("-", 1)[0] if "-" in issue_key else None):
            return AnalyticsReportResponse(filters={}, table=[])
        issue = db.execute(
            apply_issue_scope(select(JiraIssue).where(JiraIssue.key == issue_key).limit(1))
        ).scalar_one_or_none()
        if issue is None:
            return AnalyticsReportResponse(filters={}, table=[])
        month_start = period_month
        wl_stmt = apply_worklog_issue_scope(select(JiraWorklog).where(JiraWorklog.issue_id == issue.id))
        if month_start:
            from app.jira_analytics.allocation.allocation_service import _next_month_start

            wl_stmt = wl_stmt.where(JiraWorklog.started_at >= month_start).where(
                JiraWorklog.started_at < _next_month_start(month_start)
            )
        worklogs = db.execute(wl_stmt).scalars().all()
        table = [
            DrilldownPeopleWorklogRow(
                person=wl.author_display_name or "Unknown",
                role="Developer",
                issue_key=issue_key,
                worklog_date=wl.started_at.date().isoformat() if wl.started_at else None,
                direct_hours=float(wl.time_spent_seconds) / 3600.0,
                allocated_hours=0.0,
                allocation_kind="direct_worklog",
                source="Jira Worklog",
            )
            for wl in worklogs
        ]
        return AnalyticsReportResponse(
            filters={"issue_key": issue_key},
            table=[r.model_dump() for r in table],
        )

    stmt = select(MonthlyAllocatedEffort).where(MonthlyAllocatedEffort.allocation_kind != "shared_overhead")
    if period_month:
        stmt = stmt.where(MonthlyAllocatedEffort.period_month == period_month)
    if feature_key:
        stmt = stmt.where(MonthlyAllocatedEffort.feature_key == feature_key)
    rows = db.execute(scope_monthly_allocated_effort(stmt)).scalars().all()
    table = [
        DrilldownPeopleWorklogRow(
            person=r.source_display_name,
            role=r.source_role_name,
            issue_key=r.issue_key,
            worklog_date=r.period_month.isoformat(),
            direct_hours=float(r.hours) if r.allocation_kind == "direct_worklog" else 0.0,
            allocated_hours=float(r.hours) if r.allocation_kind == "indirect_allocated" else 0.0,
            allocation_kind=r.allocation_kind,
            source="HR Allocation" if r.allocation_kind == "indirect_allocated" else "Jira Worklog",
        )
        for r in rows
    ]
    return AnalyticsReportResponse(filters={}, table=[r.model_dump() for r in table])


def allocation_explain(
    db: Session,
    *,
    period_month: date,
    feature_key: str | None = None,
    issue_key: str | None = None,
    person: str | None = None,
) -> AnalyticsReportResponse:
    stmt = select(MonthlyAllocatedEffort).where(MonthlyAllocatedEffort.period_month == period_month)
    if feature_key:
        stmt = stmt.where(MonthlyAllocatedEffort.feature_key == feature_key)
    if issue_key:
        stmt = stmt.where(MonthlyAllocatedEffort.issue_key == issue_key)
    if person:
        stmt = stmt.where(MonthlyAllocatedEffort.source_display_name == person)
    rows = db.execute(scope_monthly_allocated_effort(stmt)).scalars().all()
    return AnalyticsReportResponse(
        filters={"period_month": period_month.isoformat()},
        table=[
            {
                "person": r.source_display_name,
                "role": r.source_role_name,
                "allocation_kind": r.allocation_kind,
                "hours": float(r.hours),
                "rule_snapshot": r.rule_snapshot_json,
            }
            for r in rows
        ],
    )
