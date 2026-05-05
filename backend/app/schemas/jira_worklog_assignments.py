from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


WorklogRole = Literal["pm", "dev", "qa"]


class JiraWorklogUserAssignment(BaseModel):
    jira_account_id: str = Field(min_length=1, max_length=128)
    role: WorklogRole
    team: str = Field(min_length=1, max_length=255)


class WorklogAuthorListItem(BaseModel):
    jira_account_id: str | None
    author: str | None


class WorklogAuthorListResponse(BaseModel):
    items: list[WorklogAuthorListItem]
    page: int
    size: int
    total_elements: int
    total_pages: int
    has_next: bool
    has_previous: bool
