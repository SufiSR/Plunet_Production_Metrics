from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Trend(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    STABLE = "STABLE"


class PerformanceLevel(str, Enum):
    ELITE = "ELITE"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class PeriodType(str, Enum):
    WEEK = "WEEK"
    MONTH = "MONTH"
    QUARTER = "QUARTER"


class LeadTimeBreakdownParam(str, Enum):
    """Optional lead-time disaggregation (DEVOPS-510). ``none`` preserves legacy clients."""

    none = "none"
    branch = "branch"
    stream = "stream"


class LeadTimeBreakdownBucket(BaseModel):
    median_lead_time_minutes: int | None = None
    sample_count: int = 0
    dev_review_median_minutes: int | None = None
    release_wait_median_minutes: int | None = None


class MetricValue(BaseModel):
    value: float | None
    unit: str
    display_value: str | None = None
    trend: Trend | None = None
    trend_percentage: float | None = None
    performance_level: PerformanceLevel | None = None


class LeadTimeDiagnostics(BaseModel):
    """Transparency for MR-based DORA lead time (aggregated across snapshot rows in the window)."""

    definition: str = (
        "Median lead time uses merged MRs only: earliest commit on the MR to first customer-release "
        "tag containing the merge result. MRs are ingested from configured target branches plus any "
        "additional merge branches."
    )
    sample_count: int = Field(
        ge=0,
        description="Count of MRs with a numeric lead_time in the underlying snapshot cells (summed).",
    )
    match_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Merge rows in the window keyed by lead_time_match_status (summed across cells).",
    )


class CurrentMetricsResponse(BaseModel):
    deployment_frequency: MetricValue
    lead_time: MetricValue
    change_failure_rate: MetricValue
    mttr: MetricValue
    overall_performance_level: PerformanceLevel | None
    period_start: date
    period_end: date
    repository_count: int
    generated_at: datetime
    mttr_alpha: MetricValue | None = None
    dev_review_time: MetricValue | None = None
    release_wait_time: MetricValue | None = None
    lead_time_diagnostics: LeadTimeDiagnostics | None = None
    lead_time_by_branch: dict[str, LeadTimeBreakdownBucket] | None = None
    lead_time_by_stream: dict[str, LeadTimeBreakdownBucket] | None = None


class PerformanceLevels(BaseModel):
    overall: PerformanceLevel | None
    deployment_frequency: PerformanceLevel | None
    lead_time: PerformanceLevel | None
    change_failure_rate: PerformanceLevel | None
    mttr: PerformanceLevel | None


class HistoryDataPoint(BaseModel):
    period_start: date
    period_end: date
    deployment_frequency: float | None
    lead_time_minutes: int | None
    lead_time_sample_count: int | None = None
    change_failure_rate: float | None
    mttr_minutes: int | None
    mttr_alpha_minutes: int | None = None
    dev_review_median_minutes: int | None = None
    release_wait_median_minutes: int | None = None
    performance_level: PerformanceLevels
    lead_time_by_branch: dict[str, LeadTimeBreakdownBucket] | None = None
    lead_time_by_stream: dict[str, LeadTimeBreakdownBucket] | None = None


class Pagination(BaseModel):
    page: int
    size: int
    total_elements: int
    total_pages: int
    has_next: bool
    has_previous: bool


class HistoryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    period_type: PeriodType
    from_date: date = Field(validation_alias="from", serialization_alias="from")
    to_date: date = Field(validation_alias="to", serialization_alias="to")
    repository_id: int | None
    data: list[HistoryDataPoint]
    pagination: Pagination
