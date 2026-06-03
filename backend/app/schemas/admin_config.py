from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.schemas.jira_worklog_assignments import JiraWorklogUserAssignment


class AdminConfigResponse(BaseModel):
    environment: str
    gitlab_url: str
    gitlab_token_hint: str | None
    gitlab_project_paths: list[str]
    target_branches: list[str]
    additional_merge_target_branches: list[str]
    non_customer_release_markers: list[str]
    exclude_release_only_mrs_from_lead_time: bool
    release_mr_title_markers: list[str]
    release_mr_source_branch_markers: list[str]
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
    hrworks_sync_cron_day_of_week: str
    hrworks_sync_cron_hour: int
    hrworks_sync_cron_minute: int
    jira_analytics_sync_cron_hour: int
    jira_analytics_sync_cron_minute: int
    jira_analytics_scheduled_lookback_days: int
    notifications_webhook_url: str | None
    jira_worklog_user_assignments: list[JiraWorklogUserAssignment] = Field(default_factory=list)


class AdminConfigPatch(BaseModel):
    environment: str | None = None
    gitlab_url: str | None = None
    gitlab_token: str | None = None
    gitlab_project_paths: list[str] | None = None
    target_branches: list[str] | None = None
    additional_merge_target_branches: list[str] | None = None
    non_customer_release_markers: list[str] | None = None
    exclude_release_only_mrs_from_lead_time: bool | None = None
    release_mr_title_markers: list[str] | None = None
    release_mr_source_branch_markers: list[str] | None = None
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
    hrworks_sync_cron_day_of_week: str | None = None
    hrworks_sync_cron_hour: int | None = Field(default=None, ge=0, le=23)
    hrworks_sync_cron_minute: int | None = Field(default=None, ge=0, le=59)
    jira_analytics_sync_cron_hour: int | None = Field(default=None, ge=0, le=23)
    jira_analytics_sync_cron_minute: int | None = Field(default=None, ge=0, le=59)
    jira_analytics_scheduled_lookback_days: int | None = Field(default=None, ge=1, le=3650)
    notifications_webhook_url: str | None = None
    jira_worklog_user_assignments: list[JiraWorklogUserAssignment] | None = None

    @field_validator("jira_worklog_user_assignments")
    @classmethod
    def _unique_assignment_account_ids(
        cls, v: list[JiraWorklogUserAssignment] | None
    ) -> list[JiraWorklogUserAssignment] | None:
        if v is None:
            return None
        seen: set[str] = set()
        for a in v:
            aid = (a.jira_account_id or "").strip()
            author = (a.author or "").strip().lower()
            key = f"aid:{aid}" if aid else f"author:{author}"
            if key in seen:
                raise ValueError(f"Duplicate jira_worklog_user_assignments entry: {key}")
            seen.add(key)
        return v


class WebhookTestRequest(BaseModel):
    webhook_url: HttpUrl | None = None


class WebhookTestResponse(BaseModel):
    delivered: bool
    effective_webhook_url: str
    payload: dict[str, Any]
