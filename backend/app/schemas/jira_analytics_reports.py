from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RowType = Literal["feature", "other_bug", "other_feature", "other_misc"]


class FeatureHoursPeriodHours(BaseModel):
    period: str
    hours: float = Field(ge=0)


class FeatureHoursMatrixRow(BaseModel):
    row_id: str
    label: str
    row_type: RowType
    root_key: str | None = None
    feature_name: str | None = None
    start_date: str | None = None
    target_end_date: str | None = None
    delivery_progress: str | None = None
    team_name: str | None = None
    hours_by_period: dict[str, float] = Field(default_factory=dict)
    total_hours: float = Field(ge=0, default=0)


class FeatureHoursMatrixResponse(BaseModel):
    periods: list[str]
    rows: list[FeatureHoursMatrixRow]
    jira_base_url: str
    role_filter: str | None = None
    team_filter: str | None = None
    available_roles: list[str]
    available_teams: list[str]


class FeatureHoursDrilldownIssue(BaseModel):
    issue_key: str
    issue_url: str
    summary: str | None
    issue_type_name: str | None
    depth: int
    hours_by_period: dict[str, float] = Field(default_factory=dict)
    total_hours: float = Field(ge=0, default=0)
    multi_feature: bool = False
    other_feature_keys: list[str] = Field(default_factory=list)


class FeatureHoursDrilldownSection(BaseModel):
    epic_key: str | None
    epic_url: str | None = None
    epic_summary: str | None
    total_hours: float = Field(ge=0, default=0)
    issues: list[FeatureHoursDrilldownIssue]


class FeatureHoursDrilldownResponse(BaseModel):
    row_id: str
    row_label: str
    row_type: RowType
    feature_root_key: str
    feature_summary: str | None
    row_url: str | None = None
    periods: list[str]
    sections: list[FeatureHoursDrilldownSection]
    role_filter: str | None = None
    team_filter: str | None = None


class FeatureFamilyHoursMatrixRow(BaseModel):
    row_id: str
    family_id: int
    label: str
    feature_count: int = 0
    start_date: str | None = None
    target_end_date: str | None = None
    delivery_progress: str | None = None
    team_names: list[str] = Field(default_factory=list)
    hours_by_period: dict[str, float] = Field(default_factory=dict)
    total_hours: float = Field(ge=0, default=0)


class FeatureFamilyHoursMatrixResponse(BaseModel):
    periods: list[str]
    rows: list[FeatureFamilyHoursMatrixRow]
    jira_base_url: str
    role_filter: str | None = None
    team_filter: str | None = None
    available_roles: list[str]
    available_teams: list[str]


class FeatureFamilyDrilldownFeature(BaseModel):
    root_key: str
    feature_name: str
    row_url: str | None = None
    start_date: str | None = None
    target_end_date: str | None = None
    delivery_progress: str | None = None
    team_name: str | None = None
    hours_by_period: dict[str, float] = Field(default_factory=dict)
    total_hours: float = Field(ge=0, default=0)
    sections: list[FeatureHoursDrilldownSection] = Field(default_factory=list)


class FeatureFamilyHoursDrilldownResponse(BaseModel):
    row_id: str
    family_id: int
    row_label: str
    periods: list[str]
    features: list[FeatureFamilyDrilldownFeature]
    role_filter: str | None = None
    team_filter: str | None = None


class DataQualityCheck(BaseModel):
    check_id: str
    label: str
    count: int = 0
    ignored_count: int = 0
    affected_hours: float | None = None
    severity: Literal["low", "medium", "high"] = "medium"


class DataQualityPayload(BaseModel):
    warnings: list[DataQualityCheck] = Field(default_factory=list)
    unclassified_hours: float = 0
    missing_role_assignments: int = 0


class DataQualityResponse(BaseModel):
    filters: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    data_quality: DataQualityPayload = Field(default_factory=DataQualityPayload)


class DataQualityUserDrilldownRow(BaseModel):
    user_id: int | None = None
    account_id: str
    display_name: str | None = None
    email_address: str | None = None
    jira_active: bool | None = None
    reporting_excluded: bool = False
    role_name: str | None = None
    team_name: str | None = None
    worklog_count: int = Field(ge=0)
    total_hours: float = Field(ge=0)
    first_worklog_at: datetime | None = None
    last_worklog_at: datetime | None = None
    ignored: bool = False
    ignore_reason: str | None = None
    can_ignore: bool = True


class DataQualityUserDrilldownResponse(BaseModel):
    check_id: str
    label: str
    active_count: int = Field(ge=0)
    ignored_count: int = Field(ge=0)
    users: list[DataQualityUserDrilldownRow]
    people_data_restricted: bool = False


class DataQualityUserIgnoreRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class DrilldownLinks(BaseModel):
    topics: str | None = None
    issues: str | None = None
    people: str | None = None


class AnalyticsReportResponse(BaseModel):
    filters: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    series: list[dict[str, Any]] = Field(default_factory=list)
    table: list[dict[str, Any]] = Field(default_factory=list)
    drilldowns: DrilldownLinks | None = None
    data_quality: DataQualityPayload | None = None


class DrilldownTopicRow(BaseModel):
    topic_type: str
    feature_key: str | None = None
    feature_name: str | None = None
    team: str | None = None
    direct_hours: float = 0
    allocated_hours: float = 0
    total_hours: float = 0


class DrilldownIssueRow(BaseModel):
    issue_key: str
    summary: str | None = None
    issue_type: str | None = None
    status: str | None = None
    team: str | None = None
    feature_root_key: str | None = None
    hours: float = 0
    allocation_kind: str | None = None


class DrilldownPeopleWorklogRow(BaseModel):
    person: str
    role: str | None = None
    issue_key: str | None = None
    worklog_date: str | None = None
    direct_hours: float = 0
    allocated_hours: float = 0
    allocation_kind: str | None = None
    source: str | None = None
