from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, aliased

from app.jira_analytics.models import JiraIssue, JiraIssueStatusTransition, JiraProject
from app.jira_analytics.project_scope import apply_issue_scope, filter_excluded_keys

IssueProject = aliased(JiraProject)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(slots=True)
class StatusInterval:
    issue_id: int
    issue_key: str
    project_key: str | None
    issue_type_name: str | None
    status_name: str
    interval_start: datetime
    interval_end: datetime | None
    duration_seconds: float


def _apply_interval_scope_filters(
    stmt,
    *,
    project_keys: list[str] | None,
    date_from: date | None,
    date_to: date | None,
):
    if project_keys:
        scoped_keys = filter_excluded_keys(project_keys)
        if scoped_keys:
            stmt = stmt.where(IssueProject.key.in_(scoped_keys))
    if date_to is not None:
        range_end = datetime.combine(date_to, time.max, tzinfo=timezone.utc)
        stmt = stmt.where(JiraIssueStatusTransition.changed_at <= range_end)
    if date_from is not None:
        range_start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        stmt = stmt.where(
            or_(
                JiraIssueStatusTransition.changed_at >= range_start,
                JiraIssue.resolved_at_jira.is_(None),
                JiraIssue.resolved_at_jira >= range_start,
            )
        )
    return stmt


def build_status_intervals(
    db: Session,
    issue_ids: list[int] | None = None,
    *,
    project_keys: list[str] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[StatusInterval]:
    stmt = apply_issue_scope(
        select(
            JiraIssueStatusTransition.issue_id,
            JiraIssue.key,
            IssueProject.key,
            JiraIssue.issue_type_name,
            JiraIssueStatusTransition.to_status_name,
            JiraIssueStatusTransition.changed_at,
            JiraIssue.resolved_at_jira,
        )
        .select_from(JiraIssueStatusTransition)
        .join(JiraIssue, JiraIssue.id == JiraIssueStatusTransition.issue_id)
        .outerjoin(IssueProject, IssueProject.id == JiraIssue.project_id)
        .order_by(JiraIssueStatusTransition.issue_id, JiraIssueStatusTransition.changed_at)
    )
    if issue_ids:
        if len(issue_ids) <= 1000:
            stmt = stmt.where(JiraIssueStatusTransition.issue_id.in_(issue_ids))
        else:
            stmt = stmt.where(
                or_(
                    *[
                        JiraIssueStatusTransition.issue_id.in_(issue_ids[offset : offset + 1000])
                        for offset in range(0, len(issue_ids), 1000)
                    ]
                )
            )
    else:
        stmt = _apply_interval_scope_filters(
            stmt,
            project_keys=project_keys,
            date_from=date_from,
            date_to=date_to,
        )
    rows = db.execute(stmt).all()
    by_issue: dict[int, list] = {}
    for issue_id, key, project_key, issue_type_name, status, changed_at, resolved in rows:
        by_issue.setdefault(issue_id, []).append(
            (key, project_key, issue_type_name, status, changed_at, resolved)
        )
    intervals: list[StatusInterval] = []
    now = datetime.now(timezone.utc)
    for issue_id, items in by_issue.items():
        key = items[0][0]
        project_key = items[0][1]
        issue_type_name = items[0][2]
        resolved = _as_utc(items[0][5])
        end_default = resolved or now
        for i, (_, _, _, status, start, _) in enumerate(items):
            if not status:
                continue
            end = items[i + 1][4] if i + 1 < len(items) else end_default
            start_utc = _as_utc(start)
            end_utc = _as_utc(end) if end is not None else now
            if start_utc is None:
                continue
            duration = max(0.0, (end_utc - start_utc).total_seconds())
            intervals.append(
                StatusInterval(
                    issue_id=issue_id,
                    issue_key=key,
                    project_key=project_key,
                    issue_type_name=issue_type_name,
                    status_name=status,
                    interval_start=start_utc,
                    interval_end=end_utc if i + 1 < len(items) else _as_utc(end_default),
                    duration_seconds=duration,
                )
            )
    return intervals
