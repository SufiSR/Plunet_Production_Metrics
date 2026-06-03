from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.jira_analytics.models import AllocationRoleRule, JiraUser, JiraUserRoleAssignment
from app.schemas.jira_user_admin import (
    AllocationRoleRuleItem,
    AllocationRoleRulesResponse,
    JiraUserAdminItem,
    JiraUserAdminListResponse,
    JiraUserPatch,
    JiraUserRoleAssignmentPut,
    JiraUserRoleAssignmentView,
)
from app.services.jira_user_assignments import (
    get_current_assignment_row,
    load_allocation_role_rules,
    pagination_meta,
    upsert_role_assignment,
)


def _assignment_view(row: JiraUserRoleAssignment | None) -> JiraUserRoleAssignmentView | None:
    if row is None:
        return None
    return JiraUserRoleAssignmentView(
        role_name=row.role_name,
        team_name=row.team_name,
        allocatable_percentage=row.allocatable_percentage,
        allocation_scope=row.allocation_scope,
        valid_from=row.valid_from.isoformat(),
    )


def list_jira_users_admin(
    db: Session,
    *,
    page: int,
    size: int,
    search: str | None = None,
) -> JiraUserAdminListResponse:
    filters = []
    if search and search.strip():
        q = f"%{search.strip().lower()}%"
        filters.append(
            func.lower(JiraUser.account_id).like(q)
            | func.lower(func.coalesce(JiraUser.display_name, "")).like(q)
            | func.lower(func.coalesce(JiraUser.email_address, "")).like(q)
        )
    count_stmt = select(func.count()).select_from(JiraUser)
    for f in filters:
        count_stmt = count_stmt.where(f)
    total = db.execute(count_stmt).scalar_one()
    stmt = select(JiraUser)
    for f in filters:
        stmt = stmt.where(f)
    rows = (
        db.execute(
            stmt.order_by(func.lower(func.coalesce(JiraUser.display_name, JiraUser.account_id)).asc())
            .offset(page * size)
            .limit(size)
        )
        .scalars()
        .all()
    )
    items: list[JiraUserAdminItem] = []
    for user in rows:
        assignment = get_current_assignment_row(db, jira_user_id=user.id)
        items.append(
            JiraUserAdminItem(
                id=user.id,
                account_id=user.account_id,
                display_name=user.display_name,
                email_address=user.email_address,
                jira_active=user.active,
                reporting_excluded=user.reporting_excluded,
                role_assignment=_assignment_view(assignment),
            )
        )
    meta = pagination_meta(page=page, size=size, total_elements=int(total))
    return JiraUserAdminListResponse(
        items=items,
        page=int(meta["page"]),
        size=int(meta["size"]),
        total_elements=int(meta["total_elements"]),
        total_pages=int(meta["total_pages"]),
        has_next=bool(meta["has_next"]),
        has_previous=bool(meta["has_previous"]),
    )


def patch_jira_user(db: Session, user_id: int, patch: JiraUserPatch) -> JiraUserAdminItem:
    user = db.get(JiraUser, user_id)
    if user is None:
        raise LookupError("jira_user_not_found")
    if patch.reporting_excluded is not None:
        user.reporting_excluded = patch.reporting_excluded
    db.flush()
    assignment = get_current_assignment_row(db, jira_user_id=user.id)
    return JiraUserAdminItem(
        id=user.id,
        account_id=user.account_id,
        display_name=user.display_name,
        email_address=user.email_address,
        jira_active=user.active,
        reporting_excluded=user.reporting_excluded,
        role_assignment=_assignment_view(assignment),
    )


def put_jira_user_role_assignment(
    db: Session,
    user_id: int,
    body: JiraUserRoleAssignmentPut,
) -> JiraUserAdminItem:
    user = db.get(JiraUser, user_id)
    if user is None:
        raise LookupError("jira_user_not_found")
    rules = load_allocation_role_rules(db)
    upsert_role_assignment(
        db,
        user=user,
        role_name=body.role_name.strip(),
        team_name=body.team_name,
        allocatable_percentage=body.allocatable_percentage,
        allocation_scope=body.allocation_scope,
        rules=rules,
    )
    db.commit()
    return patch_jira_user(db, user_id, JiraUserPatch())


def list_allocation_role_rules(db: Session) -> AllocationRoleRulesResponse:
    rows = db.execute(
        select(AllocationRoleRule)
        .where(AllocationRoleRule.active.is_(True))
        .order_by(AllocationRoleRule.role_name.asc())
    ).scalars().all()
    items = [
        AllocationRoleRuleItem(
            role_name=r.role_name,
            is_direct_production_role=r.is_direct_production_role,
            is_indirect_role=r.is_indirect_role,
            overhead_percentage=r.overhead_percentage,
            allocation_scope=r.allocation_scope,
            default_allocatable_percentage=Decimal(100) - Decimal(r.overhead_percentage),
        )
        for r in rows
    ]
    return AllocationRoleRulesResponse(items=items)
