from __future__ import annotations

import math
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.issue_worklog import IssueWorklog
from app.schemas.jira_worklog_assignments import JiraWorklogUserAssignment


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
        aid = (a.jira_account_id or "").strip()
        author = (a.author or "").strip().lower()
        key = f"aid:{aid}" if aid else f"author:{author}"
        if key in seen:
            raise ValueError(f"Duplicate assignment key in assignments: {key}")
        seen.add(key)


def normalize_assignments_for_patch(
    raw: list[dict[str, Any]] | None,
) -> list[JiraWorklogUserAssignment] | None:
    if raw is None:
        return None
    parsed = [JiraWorklogUserAssignment.model_validate(x) for x in raw]
    validate_unique_assignments(parsed)
    return parsed


def _distinct_authors_select():
    return select(IssueWorklog.jira_account_id, IssueWorklog.author).distinct()


def list_distinct_worklog_authors_page(
    db: Session,
    *,
    page: int,
    size: int,
) -> tuple[list[tuple[str | None, str | None]], int]:
    # Postgres: SELECT DISTINCT ... ORDER BY expressions not in SELECT is invalid (42P10).
    # Distinct pairs in a subquery, then sort/paginate in the outer SELECT.
    base = _distinct_authors_select()
    authors_sq = base.subquery()
    total = int(db.execute(select(func.count()).select_from(authors_sq)).scalar_one())

    stmt = (
        select(authors_sq.c.jira_account_id, authors_sq.c.author)
        .select_from(authors_sq)
        .order_by(
            func.lower(func.coalesce(authors_sq.c.author, "")).asc(),
            func.coalesce(authors_sq.c.jira_account_id, "").asc(),
        )
        .offset(page * size)
        .limit(size)
    )
    rows = db.execute(stmt).all()
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
