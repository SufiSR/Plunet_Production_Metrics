from __future__ import annotations

from datetime import date

from sqlalchemy import and_, distinct, func, select
from sqlalchemy.orm import Session

from app.jira_analytics.data_quality import (
    REPORTING_EXCLUDED_USERS_WITH_WORKLOGS_CHECK_ID,
    USER_DATA_QUALITY_CHECK_IDS,
    WORKLOG_USERS_WITHOUT_ASSIGNMENT_CHECK_ID,
    active_assignment_accounts_stmt,
)
from app.jira_analytics.models import JiraDataQualityUserIgnore, JiraUser, JiraWorklog
from app.jira_analytics.project_scope import apply_worklog_issue_scope
from app.schemas.jira_analytics_reports import (
    DataQualityUserDrilldownResponse,
    DataQualityUserDrilldownRow,
)
from app.services.jira_user_assignments import get_current_assignment_row

CHECK_LABELS = {
    WORKLOG_USERS_WITHOUT_ASSIGNMENT_CHECK_ID: "Worklog users without active role assignment",
    REPORTING_EXCLUDED_USERS_WITH_WORKLOGS_CHECK_ID: "Reporting-excluded users have worklogs in scope",
}


def _validate_user_check_id(check_id: str) -> str:
    normalized = check_id.strip()
    if normalized not in USER_DATA_QUALITY_CHECK_IDS:
        raise ValueError("Unsupported data quality user drilldown check")
    return normalized


def _user_findings_query(check_id: str):
    today = date.today()
    active_assignment_accounts = active_assignment_accounts_stmt(today)
    ignore_join = and_(
        JiraDataQualityUserIgnore.check_id == check_id,
        JiraDataQualityUserIgnore.jira_user_id == JiraUser.id,
        JiraDataQualityUserIgnore.active.is_(True),
    )
    stmt = (
        select(
            JiraUser.id.label("user_id"),
            JiraUser.account_id.label("user_account_id"),
            JiraUser.display_name.label("user_display_name"),
            JiraUser.email_address.label("user_email_address"),
            JiraUser.active.label("jira_active"),
            JiraUser.reporting_excluded.label("reporting_excluded"),
            JiraWorklog.author_account_id.label("author_account_id"),
            JiraWorklog.author_display_name.label("author_display_name"),
            JiraWorklog.author_email_address.label("author_email_address"),
            func.count(distinct(JiraWorklog.id)).label("worklog_count"),
            func.coalesce(func.sum(JiraWorklog.time_spent_seconds), 0).label("time_spent_seconds"),
            func.min(JiraWorklog.started_at).label("first_worklog_at"),
            func.max(JiraWorklog.started_at).label("last_worklog_at"),
            JiraDataQualityUserIgnore.id.label("ignore_id"),
            JiraDataQualityUserIgnore.reason.label("ignore_reason"),
        )
        .select_from(JiraWorklog)
        .outerjoin(JiraUser, JiraUser.account_id == JiraWorklog.author_account_id)
        .outerjoin(JiraDataQualityUserIgnore, ignore_join)
        .where(JiraWorklog.author_account_id.is_not(None))
    )
    if check_id == WORKLOG_USERS_WITHOUT_ASSIGNMENT_CHECK_ID:
        stmt = stmt.where(~JiraWorklog.author_account_id.in_(active_assignment_accounts))
    elif check_id == REPORTING_EXCLUDED_USERS_WITH_WORKLOGS_CHECK_ID:
        stmt = stmt.where(JiraUser.reporting_excluded.is_(True))
    stmt = stmt.group_by(
        JiraUser.id,
        JiraUser.account_id,
        JiraUser.display_name,
        JiraUser.email_address,
        JiraUser.active,
        JiraUser.reporting_excluded,
        JiraWorklog.author_account_id,
        JiraWorklog.author_display_name,
        JiraWorklog.author_email_address,
        JiraDataQualityUserIgnore.id,
        JiraDataQualityUserIgnore.reason,
    ).order_by(
        JiraDataQualityUserIgnore.id.is_not(None).asc(),
        func.lower(func.coalesce(JiraUser.display_name, JiraWorklog.author_display_name, JiraWorklog.author_account_id)).asc(),
    )
    return apply_worklog_issue_scope(stmt)


def build_data_quality_user_drilldown(
    db: Session,
    *,
    check_id: str,
) -> DataQualityUserDrilldownResponse:
    normalized = _validate_user_check_id(check_id)
    rows = db.execute(_user_findings_query(normalized)).all()
    items: list[DataQualityUserDrilldownRow] = []
    active_count = 0
    ignored_count = 0
    for row in rows:
        ignored = row.ignore_id is not None
        if ignored:
            ignored_count += 1
        else:
            active_count += 1

        assignment = get_current_assignment_row(
            db,
            account_id=row.user_account_id or row.author_account_id,
            jira_user_id=row.user_id,
        )
        account_id = row.user_account_id or row.author_account_id or ""
        items.append(
            DataQualityUserDrilldownRow(
                user_id=row.user_id,
                account_id=account_id,
                display_name=row.user_display_name or row.author_display_name,
                email_address=row.user_email_address or row.author_email_address,
                jira_active=row.jira_active,
                reporting_excluded=bool(row.reporting_excluded),
                role_name=assignment.role_name if assignment else None,
                team_name=assignment.team_name if assignment else None,
                worklog_count=int(row.worklog_count or 0),
                total_hours=round(float(row.time_spent_seconds or 0) / 3600.0, 2),
                first_worklog_at=row.first_worklog_at,
                last_worklog_at=row.last_worklog_at,
                ignored=ignored,
                ignore_reason=row.ignore_reason,
                can_ignore=row.user_id is not None,
            )
        )
    return DataQualityUserDrilldownResponse(
        check_id=normalized,
        label=CHECK_LABELS[normalized],
        active_count=active_count,
        ignored_count=ignored_count,
        users=items,
    )


def ignore_data_quality_user(
    db: Session,
    *,
    check_id: str,
    user_id: int,
    reason: str | None = None,
) -> DataQualityUserDrilldownResponse:
    normalized = _validate_user_check_id(check_id)
    user = db.get(JiraUser, user_id)
    if user is None:
        raise LookupError("jira_user_not_found")
    row = db.execute(
        select(JiraDataQualityUserIgnore)
        .where(JiraDataQualityUserIgnore.check_id == normalized)
        .where(JiraDataQualityUserIgnore.jira_user_id == user_id)
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        row = JiraDataQualityUserIgnore(
            check_id=normalized,
            jira_user_id=user_id,
            reason=reason.strip() if reason and reason.strip() else None,
            active=True,
        )
        db.add(row)
    else:
        row.reason = reason.strip() if reason and reason.strip() else None
        row.active = True
    db.flush()
    return build_data_quality_user_drilldown(db, check_id=normalized)


def unignore_data_quality_user(
    db: Session,
    *,
    check_id: str,
    user_id: int,
) -> DataQualityUserDrilldownResponse:
    normalized = _validate_user_check_id(check_id)
    row = db.execute(
        select(JiraDataQualityUserIgnore)
        .where(JiraDataQualityUserIgnore.check_id == normalized)
        .where(JiraDataQualityUserIgnore.jira_user_id == user_id)
        .limit(1)
    ).scalar_one_or_none()
    if row is not None:
        row.active = False
        db.flush()
    return build_data_quality_user_drilldown(db, check_id=normalized)
