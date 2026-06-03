from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import SessionDep, require_admin_session
from app.schemas.jira_user_admin import (
    AllocationRoleRulesResponse,
    JiraUserAdminItem,
    JiraUserAdminListResponse,
    JiraUserPatch,
    JiraUserRoleAssignmentPut,
)
from app.services.admin_jira_users_service import (
    list_allocation_role_rules,
    list_jira_users_admin,
    patch_jira_user,
    put_jira_user_role_assignment,
)

router = APIRouter()
AdminSessionDep = Annotated[None, Depends(require_admin_session)]


@router.get("/jira-users", response_model=JiraUserAdminListResponse)
def get_jira_users(
    _auth: AdminSessionDep,
    db: SessionDep,
    page: Annotated[int, Query(ge=0)] = 0,
    size: Annotated[int, Query(ge=1, le=500)] = 100,
    search: Annotated[str | None, Query(max_length=255)] = None,
) -> JiraUserAdminListResponse:
    return list_jira_users_admin(db, page=page, size=size, search=search)


@router.get("/jira-users/allocation-role-rules", response_model=AllocationRoleRulesResponse)
def get_allocation_role_rules(
    _auth: AdminSessionDep,
    db: SessionDep,
) -> AllocationRoleRulesResponse:
    return list_allocation_role_rules(db)


@router.patch("/jira-users/{user_id}", response_model=JiraUserAdminItem)
def patch_jira_user_endpoint(
    user_id: int,
    body: JiraUserPatch,
    _auth: AdminSessionDep,
    db: SessionDep,
) -> JiraUserAdminItem:
    try:
        item = patch_jira_user(db, user_id, body)
        db.commit()
        return item
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from None


@router.put("/jira-users/{user_id}/role-assignment", response_model=JiraUserAdminItem)
def put_jira_user_role_assignment_endpoint(
    user_id: int,
    body: JiraUserRoleAssignmentPut,
    _auth: AdminSessionDep,
    db: SessionDep,
) -> JiraUserAdminItem:
    try:
        return put_jira_user_role_assignment(db, user_id, body)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
