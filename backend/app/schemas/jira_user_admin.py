from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class JiraUserRoleAssignmentView(BaseModel):
    role_name: str | None = None
    team_name: str | None = None
    allocatable_percentage: Decimal | None = None
    allocation_scope: str | None = None
    valid_from: str | None = None


class JiraUserAdminItem(BaseModel):
    id: int
    account_id: str
    display_name: str | None
    email_address: str | None
    jira_active: bool | None
    reporting_excluded: bool
    role_assignment: JiraUserRoleAssignmentView | None = None


class JiraUserAdminListResponse(BaseModel):
    items: list[JiraUserAdminItem]
    page: int
    size: int
    total_elements: int
    total_pages: int
    has_next: bool
    has_previous: bool


class JiraUserPatch(BaseModel):
    reporting_excluded: bool | None = None


class JiraUserRoleAssignmentPut(BaseModel):
    role_name: str = Field(min_length=1, max_length=100)
    team_name: str = Field(default="", max_length=255)
    allocatable_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    allocation_scope: str | None = Field(default=None, max_length=50)

    @field_validator("allocation_scope")
    @classmethod
    def _validate_scope(cls, v: str | None) -> str | None:
        if v is None or not str(v).strip():
            return None
        key = str(v).strip().lower()
        if key not in ("team_only", "global"):
            raise ValueError("allocation_scope must be team_only or global")
        return key


class AllocationRoleRuleItem(BaseModel):
    role_name: str
    is_direct_production_role: bool
    is_indirect_role: bool
    overhead_percentage: Decimal
    allocation_scope: str
    default_allocatable_percentage: Decimal


class AllocationRoleRulesResponse(BaseModel):
    items: list[AllocationRoleRuleItem]
