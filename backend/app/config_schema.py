from __future__ import annotations

from pydantic import BaseModel, Field


class BackendConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    sync_cron_hour: int = Field(default=2, ge=0, le=23)
    sync_cron_minute: int = Field(default=0, ge=0, le=59)
    lookback_days: int = Field(default=730, ge=1)


class GitLabConfig(BaseModel):
    base_url: str = "https://gitlab.plunet.com"
    project_paths: list[str] = Field(
        default_factory=lambda: ["dev/plunet"],
        description="GitLab URL path after host (e.g. dev/plunet for https://gitlab.plunet.com/dev/plunet)",
    )
    target_branches: list[str] = Field(default_factory=lambda: ["master", "9.x", "10.x", "11.x"])
    additional_merge_target_branches: list[str] = Field(
        default_factory=list,
        description=(
            "Extra target branches for merged MR ingestion (patch/customer lines). "
            "Appended after target_branches; duplicates removed."
        ),
    )
    non_customer_release_markers: list[str] = Field(default_factory=lambda: ["rc", "beta"])
    exclude_release_only_mrs_from_lead_time: bool = True
    release_mr_title_markers: list[str] = Field(default_factory=lambda: [" release"])
    release_mr_source_branch_markers: list[str] = Field(default_factory=lambda: ["release"])


class JiraConfig(BaseModel):
    base_url: str = "https://plunet.atlassian.net"
    excluded_projects: list[str] = Field(default_factory=list)
    ready_for_qa_status_names: list[str] = Field(default_factory=lambda: ["Ready for QA"])
    production_bug_indicator_cf_ids: list[str] = Field(default_factory=list)
    mttr_alpha_priorities: list[str] = Field(default_factory=lambda: ["Critical", "Blocker"])


class NotificationsConfig(BaseModel):
    webhook_url: str | None = None


class JiraAnalyticsConfig(BaseModel):
    sync_cron_hour: int = Field(default=4, ge=0, le=23)
    sync_cron_minute: int = Field(default=30, ge=0, le=59)
    scheduled_lookback_days: int = Field(
        default=14,
        ge=1,
        description="Issues with updated >= today - N days for scheduled and default manual sync.",
    )


class HrworksConfig(BaseModel):
    base_url: str = "https://api.hrworks.de/v2"
    sync_cron_day_of_week: str = "sun"
    sync_cron_hour: int = Field(default=3, ge=0, le=23)
    sync_cron_minute: int = Field(default=0, ge=0, le=59)
    backfill_start_date: str = "2024-01-01"
    incremental_months_back: int = Field(
        default=3,
        ge=0,
        description="Months before the current month included in incremental HRWorks sync.",
    )
    incremental_forecast_months: int = Field(
        default=6,
        ge=0,
        description="Months after the current month included in incremental HRWorks sync.",
    )
    persons_batch_size: int = Field(default=1, ge=1, le=1)
    roster_refresh_hours: int = Field(default=168, ge=1)
    denied_person_ids: list[str] = Field(
        default_factory=lambda: ["jirascriptapi@plunet.com"],
    )


class ConfigurationSchema(BaseModel):
    environment: str = "development"
    backend: BackendConfig = Field(default_factory=BackendConfig)
    gitlab: GitLabConfig = Field(default_factory=GitLabConfig)
    jira: JiraConfig = Field(default_factory=JiraConfig)
    jira_analytics: JiraAnalyticsConfig = Field(default_factory=JiraAnalyticsConfig)
    hrworks: HrworksConfig = Field(default_factory=HrworksConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)
