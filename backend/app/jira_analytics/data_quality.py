from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import distinct, or_
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.jira_analytics.models import (
    JiraDataQualityUserIgnore,
    JiraFeatureMembership,
    JiraFeatureRoot,
    JiraUser,
    JiraUserRoleAssignment,
    JiraWorklog,
    MonthlyTopicEffortBase,
)
from app.jira_analytics.project_scope import (
    apply_feature_root_scope,
    apply_worklog_issue_scope,
    scope_monthly_topic_effort,
)
from app.schemas.jira_analytics_reports import DataQualityCheck, DataQualityResponse

WORKLOG_USERS_WITHOUT_ASSIGNMENT_CHECK_ID = "worklog_users_without_assignment"
REPORTING_EXCLUDED_USERS_WITH_WORKLOGS_CHECK_ID = "reporting_excluded_users_with_worklogs"
USER_DATA_QUALITY_CHECK_IDS = frozenset(
    {
        WORKLOG_USERS_WITHOUT_ASSIGNMENT_CHECK_ID,
        REPORTING_EXCLUDED_USERS_WITH_WORKLOGS_CHECK_ID,
    }
)


def active_assignment_accounts_stmt(as_of: date):
    return (
        select(JiraUserRoleAssignment.user_account_id)
        .where(JiraUserRoleAssignment.user_account_id.is_not(None))
        .where(JiraUserRoleAssignment.active.is_(True))
        .where(JiraUserRoleAssignment.valid_from <= as_of)
        .where(
            or_(
                JiraUserRoleAssignment.valid_to.is_(None),
                JiraUserRoleAssignment.valid_to >= as_of,
            )
        )
        .distinct()
    )


def ignored_user_ids_stmt(check_id: str):
    return (
        select(JiraDataQualityUserIgnore.jira_user_id)
        .where(JiraDataQualityUserIgnore.check_id == check_id)
        .where(JiraDataQualityUserIgnore.active.is_(True))
    )


def build_data_quality(db: Session) -> DataQualityResponse:
    warnings: list[DataQualityCheck] = []

    wl_no_user = db.execute(
        apply_worklog_issue_scope(
            select(func.count())
            .select_from(JiraWorklog)
            .where(JiraWorklog.author_user_id.is_(None))
            .where(JiraWorklog.author_account_id.is_(None))
        )
    ).scalar_one()
    if wl_no_user:
        warnings.append(
            DataQualityCheck(
                check_id="worklogs_without_user",
                label="Worklogs without user mapping",
                count=int(wl_no_user),
                severity="high",
            )
        )

    role_count = db.execute(select(func.count()).select_from(JiraUserRoleAssignment)).scalar_one()
    if role_count == 0:
        warnings.append(
            DataQualityCheck(
                check_id="no_role_assignments",
                label="No user role assignments configured",
                count=0,
                severity="high",
            )
        )

    today = date.today()
    active_assignment_accounts = active_assignment_accounts_stmt(today)
    ignored_missing_assignment_users = ignored_user_ids_stmt(WORKLOG_USERS_WITHOUT_ASSIGNMENT_CHECK_ID)
    wl_without_assignment = db.execute(
        apply_worklog_issue_scope(
            select(func.count(distinct(JiraWorklog.author_account_id)))
            .select_from(JiraWorklog)
            .outerjoin(JiraUser, JiraUser.account_id == JiraWorklog.author_account_id)
            .where(JiraWorklog.author_account_id.is_not(None))
            .where(~JiraWorklog.author_account_id.in_(active_assignment_accounts))
            .where(
                or_(
                    JiraUser.id.is_(None),
                    ~JiraUser.id.in_(ignored_missing_assignment_users),
                )
            )
        )
    ).scalar_one()
    ignored_wl_without_assignment = db.execute(
        apply_worklog_issue_scope(
            select(func.count(distinct(JiraWorklog.author_account_id)))
            .select_from(JiraWorklog)
            .join(JiraUser, JiraUser.account_id == JiraWorklog.author_account_id)
            .where(JiraWorklog.author_account_id.is_not(None))
            .where(~JiraWorklog.author_account_id.in_(active_assignment_accounts))
            .where(JiraUser.id.in_(ignored_missing_assignment_users))
        )
    ).scalar_one()
    if wl_without_assignment:
        warnings.append(
            DataQualityCheck(
                check_id=WORKLOG_USERS_WITHOUT_ASSIGNMENT_CHECK_ID,
                label="Worklog users without active role assignment",
                count=int(wl_without_assignment),
                ignored_count=int(ignored_wl_without_assignment),
                severity="high",
            )
        )

    ignored_reporting_excluded_users = ignored_user_ids_stmt(REPORTING_EXCLUDED_USERS_WITH_WORKLOGS_CHECK_ID)
    excluded_worklog_users = db.execute(
        apply_worklog_issue_scope(
            select(func.count(distinct(JiraWorklog.author_account_id)))
            .select_from(JiraWorklog)
            .join(JiraUser, JiraUser.account_id == JiraWorklog.author_account_id)
            .where(JiraUser.reporting_excluded.is_(True))
            .where(~JiraUser.id.in_(ignored_reporting_excluded_users))
        )
    ).scalar_one()
    ignored_excluded_worklog_users = db.execute(
        apply_worklog_issue_scope(
            select(func.count(distinct(JiraWorklog.author_account_id)))
            .select_from(JiraWorklog)
            .join(JiraUser, JiraUser.account_id == JiraWorklog.author_account_id)
            .where(JiraUser.reporting_excluded.is_(True))
            .where(JiraUser.id.in_(ignored_reporting_excluded_users))
        )
    ).scalar_one()
    if excluded_worklog_users:
        warnings.append(
            DataQualityCheck(
                check_id=REPORTING_EXCLUDED_USERS_WITH_WORKLOGS_CHECK_ID,
                label="Reporting-excluded users have worklogs in scope",
                count=int(excluded_worklog_users),
                ignored_count=int(ignored_excluded_worklog_users),
                severity="medium",
            )
        )

    unclassified = db.execute(
        scope_monthly_topic_effort(
            select(func.coalesce(func.sum(MonthlyTopicEffortBase.direct_hours), 0)).where(
                MonthlyTopicEffortBase.topic_type == "unclassified"
            )
        )
    ).scalar_one()
    if unclassified and Decimal(unclassified) > 0:
        warnings.append(
            DataQualityCheck(
                check_id="unclassified_hours",
                label="Unclassified direct hours in topic base",
                count=1,
                affected_hours=float(unclassified),
                severity="medium",
            )
        )

    roots_no_members = db.execute(
        apply_feature_root_scope(
            select(func.count())
            .select_from(JiraFeatureRoot)
            .where(
                ~JiraFeatureRoot.id.in_(
                    select(JiraFeatureMembership.feature_root_id).distinct()
                )
            )
        )
    ).scalar_one()
    if roots_no_members:
        warnings.append(
            DataQualityCheck(
                check_id="pmgt_roots_without_members",
                label="PMGT roots without member issues",
                count=int(roots_no_members),
                severity="low",
            )
        )

    return DataQualityResponse(
        filters={},
        summary={"warning_count": len(warnings)},
        data_quality={"warnings": warnings, "unclassified_hours": float(unclassified or 0)},
    )
