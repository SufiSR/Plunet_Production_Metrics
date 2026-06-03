from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.jira_analytics.allocation.role_mapping import (
    allocation_role_for_worklog_role,
    worklog_role_for_allocation_role,
)
from app.jira_analytics.models import (
    AllocationRoleRule,
    JiraUser,
    JiraUserRoleAssignment,
)
from app.schemas.jira_worklog_assignments import JiraWorklogUserAssignment, WorklogRole


@dataclass(frozen=True, slots=True)
class ResolvedAssignment:
    jira_user_id: int | None
    account_id: str | None
    display_name: str | None
    role_name: str
    team_name: str | None
    worklog_role: str | None
    allocatable_percentage: Decimal | None
    allocation_scope: str | None
    reporting_excluded: bool


def _today() -> date:
    return date.today()


def get_jira_user_by_account_id(db: Session, account_id: str | None) -> JiraUser | None:
    if not account_id or not str(account_id).strip():
        return None
    return db.execute(
        select(JiraUser).where(JiraUser.account_id == account_id.strip()).limit(1)
    ).scalar_one_or_none()


def is_reporting_excluded(db: Session, *, account_id: str | None, jira_user_id: int | None = None) -> bool:
    if jira_user_id is not None:
        row = db.get(JiraUser, jira_user_id)
        return bool(row and row.reporting_excluded)
    user = get_jira_user_by_account_id(db, account_id)
    return bool(user and user.reporting_excluded)


def reporting_excluded_account_ids(db: Session) -> frozenset[str]:
    rows = db.execute(
        select(JiraUser.account_id).where(JiraUser.reporting_excluded.is_(True))
    ).scalars().all()
    return frozenset(a.strip() for a in rows if a and a.strip())


def _assignment_valid_on(row: JiraUserRoleAssignment, as_of: date) -> bool:
    if not row.active:
        return False
    if row.valid_from > as_of:
        return False
    return row.valid_to is None or row.valid_to >= as_of


def _assignment_quality_score(row: JiraUserRoleAssignment) -> tuple[int, int, int]:
    team_ok = 1 if (row.team_name or "").strip() else 0
    email = (row.user_email or "").strip().lower()
    real_email = 1 if email and not email.endswith("@unknown.local") else 0
    return (team_ok, real_email, row.valid_from.toordinal())


def _prefer_best_assignment(rows: list[JiraUserRoleAssignment]) -> JiraUserRoleAssignment | None:
    active_rows = [row for row in rows if row.active]
    if not active_rows:
        return None
    return max(active_rows, key=_assignment_quality_score)


def _pick_assignment_for_period(
    rows: list[JiraUserRoleAssignment],
    as_of: date,
) -> JiraUserRoleAssignment | None:
    active_rows = [row for row in rows if row.active]
    if not active_rows:
        return None
    for row in sorted(active_rows, key=lambda item: item.valid_from, reverse=True):
        if _assignment_valid_on(row, as_of):
            return row
    previous_rows = [row for row in active_rows if row.valid_from <= as_of]
    if previous_rows:
        return _prefer_best_assignment(previous_rows)
    # Assignments are often created after historical allocation months exist.
    return _prefer_best_assignment(active_rows)


def _active_assignments_stmt():
    return (
        select(JiraUserRoleAssignment)
        .where(JiraUserRoleAssignment.active.is_(True))
        .order_by(JiraUserRoleAssignment.valid_from.asc())
    )


def _active_assignments_for_jira_user(db: Session, jira_user_id: int) -> list[JiraUserRoleAssignment]:
    return list(
        db.execute(
            _active_assignments_stmt().where(JiraUserRoleAssignment.jira_user_id == jira_user_id)
        )
        .scalars()
        .all()
    )


def _active_assignments_for_account(db: Session, account_id: str) -> list[JiraUserRoleAssignment]:
    return list(
        db.execute(
            _active_assignments_stmt().where(
                JiraUserRoleAssignment.user_account_id == account_id.strip()
            )
        )
        .scalars()
        .all()
    )


def _active_assignments_for_email(db: Session, email: str) -> list[JiraUserRoleAssignment]:
    return list(
        db.execute(
            _active_assignments_stmt().where(
                func.lower(JiraUserRoleAssignment.user_email) == email.lower()
            )
        )
        .scalars()
        .all()
    )


def _active_assignments_for_display_name(db: Session, display_name: str) -> list[JiraUserRoleAssignment]:
    return list(
        db.execute(
            _active_assignments_stmt().where(
                func.lower(JiraUserRoleAssignment.display_name) == display_name.lower()
            )
        )
        .scalars()
        .all()
    )


def _merge_assignment_candidates(*groups: list[JiraUserRoleAssignment]) -> list[JiraUserRoleAssignment]:
    merged: list[JiraUserRoleAssignment] = []
    seen: set[int] = set()
    for group in groups:
        for row in group:
            if row.id in seen:
                continue
            seen.add(row.id)
            merged.append(row)
    return merged


def get_assignment_for_allocated_source(
    db: Session,
    *,
    source_user_email: str,
    display_name: str | None = None,
    as_of: date | None = None,
) -> JiraUserRoleAssignment | None:
    """Resolve jira_user_role_assignment for a monthly_allocated_effort source key."""
    as_of = as_of or _today()
    source = (source_user_email or "").strip()
    if not source:
        return None

    candidates: list[JiraUserRoleAssignment] = []
    if "@" not in source:
        user = get_jira_user_by_account_id(db, source)
        if user is not None:
            candidates = _merge_assignment_candidates(
                candidates,
                _active_assignments_for_jira_user(db, user.id),
            )
        candidates = _merge_assignment_candidates(
            candidates,
            _active_assignments_for_account(db, source),
        )
    else:
        user = db.execute(
            select(JiraUser)
            .where(func.lower(JiraUser.email_address) == source.lower())
            .limit(1)
        ).scalar_one_or_none()
        if user is not None:
            candidates = _merge_assignment_candidates(
                candidates,
                _active_assignments_for_jira_user(db, user.id),
            )
            if user.account_id:
                candidates = _merge_assignment_candidates(
                    candidates,
                    _active_assignments_for_account(db, user.account_id),
                )
        candidates = _merge_assignment_candidates(
            candidates,
            _active_assignments_for_email(db, source),
        )

    label = (display_name or "").strip()
    if label:
        candidates = _merge_assignment_candidates(
            candidates,
            _active_assignments_for_display_name(db, label),
        )

    return _pick_assignment_for_period(candidates, as_of)


def get_current_assignment_row(
    db: Session,
    *,
    account_id: str | None = None,
    jira_user_id: int | None = None,
    as_of: date | None = None,
) -> JiraUserRoleAssignment | None:
    as_of = as_of or _today()
    candidates: list[JiraUserRoleAssignment] = []
    if jira_user_id is not None:
        candidates = _merge_assignment_candidates(
            candidates,
            _active_assignments_for_jira_user(db, jira_user_id),
        )
    if account_id and account_id.strip():
        candidates = _merge_assignment_candidates(
            candidates,
            _active_assignments_for_account(db, account_id),
        )
    if not candidates:
        return None
    return _pick_assignment_for_period(candidates, as_of)


def resolve_assignment(
    db: Session,
    *,
    account_id: str | None,
    display_name: str | None = None,
    as_of: date | None = None,
) -> ResolvedAssignment | None:
    user = get_jira_user_by_account_id(db, account_id)
    if user and user.reporting_excluded:
        return None
    row = get_current_assignment_row(
        db,
        account_id=account_id,
        jira_user_id=user.id if user else None,
        as_of=as_of,
    )
    if row is None:
        return None
    worklog_role = worklog_role_for_allocation_role(row.role_name)
    return ResolvedAssignment(
        jira_user_id=user.id if user else row.jira_user_id,
        account_id=(account_id or row.user_account_id or "").strip() or None,
        display_name=display_name or row.display_name,
        role_name=row.role_name,
        team_name=row.team_name,
        worklog_role=worklog_role,
        allocatable_percentage=row.allocatable_percentage,
        allocation_scope=row.allocation_scope,
        reporting_excluded=False,
    )


def list_worklog_assignments(db: Session, *, as_of: date | None = None) -> list[JiraWorklogUserAssignment]:
    """Legacy-shaped list for DORA swimlane role mapping."""
    as_of = as_of or _today()
    rows = db.execute(
        select(JiraUserRoleAssignment, JiraUser)
        .outerjoin(JiraUser, JiraUser.id == JiraUserRoleAssignment.jira_user_id)
        .where(JiraUserRoleAssignment.active.is_(True))
        .where(JiraUserRoleAssignment.valid_from <= as_of)
        .where(
            or_(
                JiraUserRoleAssignment.valid_to.is_(None),
                JiraUserRoleAssignment.valid_to >= as_of,
            )
        )
        .order_by(JiraUserRoleAssignment.id)
    ).all()
    out: list[JiraWorklogUserAssignment] = []
    for row, user in rows:
        if user is not None and user.reporting_excluded:
            continue
        worklog_role = worklog_role_for_allocation_role(row.role_name)
        if not worklog_role:
            continue
        account_id = user.account_id if user is not None else row.user_account_id
        author = user.display_name if user is not None else row.display_name
        out.append(
            JiraWorklogUserAssignment(
                jira_account_id=account_id,
                author=author,
                role=cast(WorklogRole, worklog_role),
                team=row.team_name or "",
            )
        )
    return out


def list_assignments_maps(
    db: Session,
    *,
    as_of: date | None = None,
) -> tuple[dict[str, tuple[str, str]], dict[str, tuple[str, str]]]:
    """account_id -> (worklog_role, team), display_name.lower() -> (worklog_role, team)."""
    as_of = as_of or _today()
    by_account: dict[str, tuple[str, str]] = {}
    by_author: dict[str, tuple[str, str]] = {}
    for item in list_worklog_assignments(db, as_of=as_of):
        pair = (item.role, item.team.strip())
        if item.jira_account_id:
            by_account[item.jira_account_id.strip()] = pair
        if item.author:
            by_author[item.author.strip().lower()] = pair
    return by_account, by_author


def load_allocation_role_rules(db: Session) -> dict[str, AllocationRoleRule]:
    rows = db.execute(
        select(AllocationRoleRule).where(AllocationRoleRule.active.is_(True))
    ).scalars().all()
    return {r.role_name: r for r in rows}


def upsert_role_assignment(
    db: Session,
    *,
    user: JiraUser,
    role_name: str,
    team_name: str,
    allocatable_percentage: Decimal | None,
    allocation_scope: str | None,
    rules: dict[str, AllocationRoleRule],
) -> JiraUserRoleAssignment:
    rule = rules.get(role_name)
    if rule is None:
        raise ValueError(f"Unknown role_name: {role_name}")
    scope = allocation_scope or rule.allocation_scope
    if scope == "team_only" and not team_name.strip():
        raise ValueError("team_name is required when allocation scope is team_only")

    today = _today()
    current = get_current_assignment_row(db, jira_user_id=user.id, as_of=today)
    team_clean = team_name.strip() or None
    if current is not None:
        unchanged = (
            current.role_name == role_name
            and (current.team_name or "") == (team_clean or "")
            and current.allocatable_percentage == allocatable_percentage
            and (current.allocation_scope or rule.allocation_scope) == scope
        )
        if unchanged:
            return current
        yesterday = today - timedelta(days=1)
        if current.valid_to is None or current.valid_to >= today:
            current.valid_to = yesterday

    row = JiraUserRoleAssignment(
        jira_user_id=user.id,
        user_account_id=user.account_id,
        user_email=user.email_address or f"{user.account_id}@unknown.local",
        display_name=user.display_name or user.account_id,
        role_name=role_name,
        team_id=team_clean,
        team_name=team_clean,
        allocatable_percentage=allocatable_percentage,
        allocation_scope=scope,
        valid_from=today,
        valid_to=None,
        active=True,
    )
    db.add(row)
    db.flush()
    return row


def import_legacy_worklog_assignments(
    db: Session,
    settings_json: dict[str, Any],
) -> int:
    """One-time helper: map settings JSON worklog roles into role_assignment rows."""
    from app.services.jira_worklog_settings import read_worklog_assignments_from_settings

    assignments = read_worklog_assignments_from_settings(settings_json)
    if not assignments:
        return 0
    rules = load_allocation_role_rules(db)
    count = 0
    for item in assignments:
        account_id = (item.jira_account_id or "").strip()
        if not account_id:
            continue
        user = get_jira_user_by_account_id(db, account_id)
        if user is None:
            user = JiraUser(
                account_id=account_id,
                display_name=(item.author or account_id).strip(),
                email_address=f"{account_id}@unknown.local",
            )
            db.add(user)
            db.flush()
        role_name = allocation_role_for_worklog_role(item.role)
        upsert_role_assignment(
            db,
            user=user,
            role_name=role_name,
            team_name=item.team,
            allocatable_percentage=None,
            allocation_scope=None,
            rules=rules,
        )
        count += 1
    return count


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
