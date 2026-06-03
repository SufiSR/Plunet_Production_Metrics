from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


WorklogRole = Literal["pm", "dev", "qa", "sup"]


class JiraWorklogUserAssignment(BaseModel):
    jira_account_id: str | None = Field(default=None, min_length=1, max_length=128)
    author: str | None = Field(default=None, min_length=1, max_length=255)
    role: WorklogRole
    team: str = Field(default="", max_length=255)

    @model_validator(mode="after")
    def _require_identity(self) -> "JiraWorklogUserAssignment":
        has_account = bool((self.jira_account_id or "").strip())
        has_author = bool((self.author or "").strip())
        if not has_account and not has_author:
            raise ValueError("Either jira_account_id or author must be provided")
        return self

