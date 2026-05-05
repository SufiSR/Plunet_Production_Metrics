from __future__ import annotations

import math
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.issue_worklog import IssueWorklog
from app.schemas.jira_worklog_assignments import JiraWorklogUserAssignment


def read_worklog_denylist_from_settings(settings_json: dict[str, Any]) -> list[str]:
    jr = settings_json.get("jira")
    if not isinstance(jr, dict):
        return []
    raw = jr.get("jira_worklog_author_denylist")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        s = str(item).strip()
        if s:
            out.append(s)
    return list(dict.fromkeys(out))


def read_worklog_assignments_from_settings(
    settings_json: dict[str, Any],
) -> list[JiraWorklogUserAssignment]:
    jr = settings_json.get("jira")
    if not isinstance(jr, dict):
        return []
    raw = jr.get("jira_worklog_user_assignments")
    if not isinstance(raw, list):
        return []
    out: list[JiraWorklogUserAssignment] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            out.append(JiraWorklogUserAssignment.model_validate(item))
        except Exception:
            continue
    return out


def validate_unique_assignments(assignments: list[JiraWorklogUserAssignment]) -> None:
    seen: set[str] = set()
    for a in assignments:
        key = a.jira_account_id.strip()
        if key in seen:
            raise ValueError(f"Duplicate jira_account_id in assignments: {key}")
        seen.add(key)


def normalize_assignments_for_patch(
    raw: list[dict[str, Any]] | None,
) -> list[JiraWorklogUserAssignment] | None:
    if raw is None:
        return None
    parsed = [JiraWorklogUserAssignment.model_validate(x) for x in raw]
    validate_unique_assignments(parsed)
    return parsed


def normalize_denylist_for_patch(raw: list[str] | None) -> list[str] | None:
    if raw is None:
        return None
    out: list[str] = []
    for item in raw:
        s = str(item).strip()
        if s:
            out.append(s)
    return list(dict.fromkeys(out))


def _distinct_authors_select(denylist: list[str]):
    deny_set = set(denylist)
    base = select(IssueWorklog.jira_account_id, IssueWorklog.author).distinct()
    if deny_set:
        base = base.where(
            IssueWorklog.jira_account_id.is_(None)
            | (~IssueWorklog.jira_account_id.in_(tuple(deny_set))))
    return base


def list_distinct_worklog_authors_page(
    db: Session,
    *,
    denylist: list[str],
    page: int,
    size: int,
) -> tuple[list[tuple[str | None, str | None]], int]:
    base = _distinct_authors_select(denylist)
    sub = base.subquery()
    total = int(db.execute(select(func.count()).select_from(sub)).scalar_one())
    sorted_rows = (
        base.order_by(
            func.lower(func.coalesce(IssueWorklog.author, "")).asc(),
            func.coalesce(IssueWorklog.jira_account_id, "").asc(),
        )
        .offset(page * size)
        .limit(size)
    )
    rows = db.execute(sorted_rows).all()
    tuples = [(r[0], r[1]) for r in rows]
    return tuples, total


def pagination_meta(*, page: int, size: int, total_elements: int) -> dict[str, int | bool]:
    total_pages = max(1, math.ceil(total_elements / size)) if size and total_elements else 0
    if total_elements == 0:
        total_pages = 0
    return {
        "page": page,
        "size": size,
        "total_elements": total_elements,
        "total_pages": total_pages,
        "has_next": size > 0 and (page + 1) * size < total_elements,
        "has_previous": page > 0 and total_elements > 0,
    }
