from __future__ import annotations

from typing import Optional

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
    project_paths: list[str] = Field(default_factory=list)
    target_branches: list[str] = Field(default_factory=lambda: ["master", "9.x", "10.x", "11.x"])
    non_customer_release_markers: list[str] = Field(default_factory=lambda: ["rc", "beta"])


class JiraConfig(BaseModel):
    base_url: str = "https://plunet.atlassian.net"
    excluded_projects: list[str] = Field(default_factory=list)
    ready_for_qa_status_names: list[str] = Field(default_factory=lambda: ["Ready for QA"])
    production_bug_indicator_cf_ids: list[str] = Field(default_factory=list)


class NotificationsConfig(BaseModel):
    webhook_url: Optional[str] = None


class ConfigurationSchema(BaseModel):
    environment: str = "development"
    backend: BackendConfig = Field(default_factory=BackendConfig)
    gitlab: GitLabConfig = Field(default_factory=GitLabConfig)
    jira: JiraConfig = Field(default_factory=JiraConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)
