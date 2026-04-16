from __future__ import annotations

from pydantic import BaseModel, Field


class AdminConfigResponse(BaseModel):
    environment: str
    gitlab_url: str
    gitlab_token_hint: str | None
    gitlab_project_paths: list[str]
    target_branches: list[str]
    additional_merge_target_branches: list[str]
    non_customer_release_markers: list[str]
    jira_url: str
    jira_username: str
    jira_token_hint: str | None
    excluded_projects: list[str]
    ready_for_qa_status_names: list[str]
    production_bug_indicator_cf_ids: list[str]
    mttr_alpha_priorities: list[str]
    sync_cron_hour: int
    sync_cron_minute: int
    lookback_days: int
    notifications_webhook_url: str | None


class AdminConfigPatch(BaseModel):
    environment: str | None = None
    gitlab_url: str | None = None
    gitlab_token: str | None = None
    gitlab_project_paths: list[str] | None = None
    target_branches: list[str] | None = None
    additional_merge_target_branches: list[str] | None = None
    non_customer_release_markers: list[str] | None = None
    jira_url: str | None = None
    jira_username: str | None = None
    jira_token: str | None = None
    excluded_projects: list[str] | None = None
    ready_for_qa_status_names: list[str] | None = None
    production_bug_indicator_cf_ids: list[str] | None = None
    mttr_alpha_priorities: list[str] | None = None
    sync_cron_hour: int | None = Field(default=None, ge=0, le=23)
    sync_cron_minute: int | None = Field(default=None, ge=0, le=59)
    lookback_days: int | None = Field(default=None, ge=1)
    notifications_webhook_url: str | None = None
