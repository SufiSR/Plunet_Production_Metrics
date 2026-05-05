from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ReleaseTimelineItem(BaseModel):
    repository_id: int
    repository_path: str
    tag_name: str
    committed_at: datetime
    customer_release: bool
    version_major: int | None
    version_minor: int | None
    version_patch: int | None


class ReleaseTimelineResponse(BaseModel):
    items: list[ReleaseTimelineItem]
    total: int


class ReleaseWorklogHoursByRole(BaseModel):
    pm: float
    dev: float
    qa: float
    unmapped: float


class ReleaseWorklogTeamHoursRow(BaseModel):
    team: str
    hours: float


class ReleaseWorklogHoursResponse(BaseModel):
    repository_id: int
    tag_name: str
    hours_by_role: ReleaseWorklogHoursByRole
    hours_by_team: list[ReleaseWorklogTeamHoursRow]
    unmapped_team_hours: float
    total_hours: float


class OffsetPagination(BaseModel):
    page: int = Field(ge=0)
    size: int = Field(ge=1)
    total_elements: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    has_next: bool
    has_previous: bool


class CustomerReleaseDrilldownItem(BaseModel):
    repository_id: int
    repository_path: str
    tag_name: str
    committed_at: datetime
    version_major: int | None
    version_minor: int | None
    version_patch: int | None
    lane: str
    mr_count: int


class CustomerReleaseDrilldownListResponse(BaseModel):
    items: list[CustomerReleaseDrilldownItem]
    pagination: OffsetPagination


class ReleaseMergeRequestRow(BaseModel):
    gitlab_mr_id: int
    title: str | None
    target_branch: str
    merged_at: datetime
    lead_time_hours: float | None
    release_wait_time_hours: float | None
    jira_key: str | None
    included_in_lead_time_metrics: bool


class ReleaseMergeRequestListResponse(BaseModel):
    repository_id: int
    tag_name: str
    items: list[ReleaseMergeRequestRow]
    pagination: OffsetPagination
    previous_customer_tag: str | None = None
    gitlab_compare_url: str | None = None
    mr_with_jira_key_count: int = 0


class FailedCustomerReleaseDrilldownItem(BaseModel):
    repository_id: int
    repository_path: str
    tag_name: str
    committed_at: datetime
    version_major: int | None
    version_minor: int | None
    version_patch: int | None
    lane: str
    mr_count: int
    issue_count: int


class FailedCustomerReleaseDrilldownListResponse(BaseModel):
    items: list[FailedCustomerReleaseDrilldownItem]
    pagination: OffsetPagination


class ReleaseProductionBugRow(BaseModel):
    jira_key: str
    summary: str | None
    status: str | None
    priority: str | None
    healthmemo: str | None
    jira_browse_url: str | None = None


class ReleaseProductionBugListResponse(BaseModel):
    repository_id: int
    tag_name: str
    items: list[ReleaseProductionBugRow]
    pagination: OffsetPagination


class MttrAlphaResolutionPathCount(BaseModel):
    resolution_path: str
    count: int


class MttrAlphaHistogramBin(BaseModel):
    """One server-side bucket of MTTR Alpha times (minutes since bug report to first fix release)."""

    label: str
    start_minutes: int = Field(ge=0)
    end_minutes: int | None = Field(
        default=None,
        description="Upper bound (minutes), exclusive; null means no upper bound.",
    )
    count: int = Field(ge=0)


class MttrAlphaSummaryResponse(BaseModel):
    period_type: str
    period_start: datetime
    period_end: datetime
    incident_count: int
    median_minutes: int | None
    p50_minutes: int | None = Field(
        default=None,
        description="Same value as median_minutes (discrete sample median) for P50 labelling.",
    )
    p75_minutes: int | None = Field(
        default=None,
        description="P75: linear interpolation between closest ranks (Type 7), rounded to whole minutes.",
    )
    p90_minutes: int | None = Field(
        default=None,
        description="P90: same convention as p75_minutes.",
    )
    p95_minutes: int | None = Field(
        default=None,
        description="P95: same convention as p75_minutes.",
    )
    min_minutes: int | None = Field(
        default=None, description="Minimum MTTR in the window (same filter as incident_count)."
    )
    max_minutes: int | None = Field(
        default=None, description="Maximum MTTR in the window (same filter as incident_count)."
    )
    resolution_paths: list[MttrAlphaResolutionPathCount]
    mttr_alpha_histogram: list[MttrAlphaHistogramBin] = Field(
        default_factory=list,
        description="Binned distribution of MTTR Alpha minutes; empty window yields zero counts in every bin.",
    )


class MttrAlphaIncidentRow(BaseModel):
    jira_key: str
    summary: str | None
    status: str | None
    priority: str | None
    healthmemo: str | None
    created_at: datetime | None
    first_fix_release_date: datetime | None
    first_fix_release_tag: str | None
    mttr_alpha_minutes: int | None
    mttr_alpha_resolution_path: str | None
    jira_browse_url: str | None = None


class MttrAlphaIncidentListResponse(BaseModel):
    period_type: str
    period_start: datetime
    period_end: datetime
    items: list[MttrAlphaIncidentRow]
    pagination: OffsetPagination


class MttrAlphaReleaseDrilldownItem(BaseModel):
    first_fix_release_tag: str
    first_fix_release_date: datetime
    issue_count: int
    median_minutes: int | None


class MttrAlphaReleaseDrilldownListResponse(BaseModel):
    period_type: str
    period_start: datetime
    period_end: datetime
    items: list[MttrAlphaReleaseDrilldownItem]
    pagination: OffsetPagination
