"""Global analytics scope: exclude non-reporting Jira projects from all reports."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import Select, or_, select
from sqlalchemy.sql import ColumnElement

from app.jira_analytics.models import (
    JiraFeatureRoot,
    JiraIssue,
    JiraProject,
    JiraWorklog,
    MonthlyAllocatedEffort,
    MonthlyTopicEffortBase,
)

EXCLUDED_PROJECT_KEYS: frozenset[str] = frozenset(
    {"ACT", "DIM", "ITS", "JIRATESTS", "PLU", "SE"}
)


def excluded_project_keys() -> frozenset[str]:
    return EXCLUDED_PROJECT_KEYS


def issue_allowed_predicate() -> ColumnElement[bool]:
    """True when the issue is not in an excluded project (unknown project is allowed)."""
    return or_(
        JiraIssue.project_id.is_(None),
        JiraProject.key.notin_(tuple(EXCLUDED_PROJECT_KEYS)),
    )


def feature_root_allowed_predicate() -> ColumnElement[bool]:
    return JiraFeatureRoot.root_project_key.notin_(tuple(EXCLUDED_PROJECT_KEYS))


def allowed_issue_ids_subquery():
    return (
        select(JiraIssue.id)
        .outerjoin(JiraProject, JiraProject.id == JiraIssue.project_id)
        .where(issue_allowed_predicate())
        .scalar_subquery()
    )


def apply_issue_scope(stmt: Select) -> Select:
    """Add project join + filter for queries that already reference JiraIssue."""
    return stmt.outerjoin(JiraProject, JiraProject.id == JiraIssue.project_id).where(
        issue_allowed_predicate()
    )


def apply_worklog_issue_scope(stmt: Select) -> Select:
    """Restrict worklog queries to issues outside globally excluded projects."""
    return stmt.where(JiraWorklog.issue_id.in_(allowed_issue_ids_subquery()))


def apply_feature_root_scope(stmt: Select) -> Select:
    return stmt.where(feature_root_allowed_predicate())


def is_excluded_project_key(key: str | None) -> bool:
    if not key:
        return False
    return key.strip().upper() in EXCLUDED_PROJECT_KEYS


def filter_excluded_keys(keys: Iterable[str]) -> list[str]:
    return [k for k in keys if not is_excluded_project_key(k)]


def scope_monthly_topic_effort(stmt: Select) -> Select:
    return stmt.where(MonthlyTopicEffortBase.issue_id.in_(allowed_issue_ids_subquery()))


def scope_monthly_allocated_effort(stmt: Select) -> Select:
    return stmt.where(
        or_(
            MonthlyAllocatedEffort.issue_id.is_(None),
            MonthlyAllocatedEffort.issue_id.in_(allowed_issue_ids_subquery()),
        )
    )
