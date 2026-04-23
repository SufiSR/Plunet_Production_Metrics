from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from statistics import median

from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import Session

from app.config_schema import ConfigurationSchema
from app.models.bug_release import BugRelease
from app.models.merge_request import MergeRequest
from app.models.production_bug import ProductionBug
from app.models.release import Release
from app.services.cfr_bug_filter import cfr_eligible_production_bug_predicate

PERIOD_TYPES = ("WEEK", "MONTH", "QUARTER")
PERFORMANCE_LEVELS = ("LOW", "MEDIUM", "HIGH", "ELITE")

_MTTR_COMPUTE_SENTINEL = object()


@dataclass(frozen=True)
class MetricValues:
    deployment_freq: Decimal
    lead_time_minutes: int | None
    dev_review_median_minutes: int | None
    release_wait_median_minutes: int | None
    change_failure_rate: Decimal
    mttr_minutes: int | None
    mttr_alpha_minutes: int | None
    lead_post_production_median_minutes: int | None
    lead_time_sample_count: int
    lead_time_match_counts: dict[str, int]


def classify_performance_level(
    *,
    deployment_freq_per_week: float | None,
    lead_time_minutes: int | None,
    change_failure_rate: float | None,
    mttr_minutes: int | None,
) -> str | None:
    if (
        deployment_freq_per_week is None
        or lead_time_minutes is None
        or change_failure_rate is None
        or mttr_minutes is None
    ):
        return None

    levels = (
        _deployment_level(deployment_freq_per_week),
        _lead_time_level(lead_time_minutes),
        _cfr_level(change_failure_rate),
        _mttr_level(mttr_minutes),
    )
    return min(levels, key=PERFORMANCE_LEVELS.index)


def calculate_period_metrics(
    session: Session,
    *,
    period_start: date,
    period_end: date,
    repository_id: int,
    config: ConfigurationSchema | None = None,
    mttr_minutes_override: int | None | object = _MTTR_COMPUTE_SENTINEL,
    mttr_alpha_minutes_override: int | None | object = _MTTR_COMPUTE_SENTINEL,
) -> MetricValues:
    runtime_config = config or ConfigurationSchema()
    start_dt, end_dt = _period_datetimes(period_start, period_end)
    deployment_freq = calculate_deployment_frequency_per_week(
        session,
        start_dt=start_dt,
        end_dt=end_dt,
        repository_id=repository_id,
    )
    lead_time_minutes = calculate_lead_time_minutes(
        session,
        start_dt=start_dt,
        end_dt=end_dt,
        repository_id=repository_id,
        config=runtime_config,
    )
    dev_review_median_minutes = calculate_dev_review_minutes(
        session,
        start_dt=start_dt,
        end_dt=end_dt,
        repository_id=repository_id,
        config=runtime_config,
    )
    release_wait_median_minutes = calculate_release_wait_minutes(
        session,
        start_dt=start_dt,
        end_dt=end_dt,
        repository_id=repository_id,
        config=runtime_config,
    )
    change_failure_rate = calculate_change_failure_rate(
        session,
        start_dt=start_dt,
        end_dt=end_dt,
        repository_id=repository_id,
    )
    if mttr_minutes_override is _MTTR_COMPUTE_SENTINEL:
        mttr_minutes = calculate_mttr_minutes(
            session,
            start_dt=start_dt,
            end_dt=end_dt,
        )
    else:
        mttr_minutes = mttr_minutes_override  # type: ignore[assignment]
    if mttr_alpha_minutes_override is _MTTR_COMPUTE_SENTINEL:
        mttr_alpha_minutes = calculate_mttr_alpha_minutes(
            session,
            start_dt=start_dt,
            end_dt=end_dt,
        )
    else:
        mttr_alpha_minutes = mttr_alpha_minutes_override  # type: ignore[assignment]
    lead_post_production_median_minutes = calculate_lead_post_production_minutes(
        session,
        start_dt=start_dt,
        end_dt=end_dt,
        repository_id=repository_id,
    )
    lt_sample, lt_counts = calculate_lead_time_diagnostics(
        session,
        start_dt=start_dt,
        end_dt=end_dt,
        repository_id=repository_id,
        config=runtime_config,
    )
    return MetricValues(
        deployment_freq=deployment_freq,
        lead_time_minutes=lead_time_minutes,
        dev_review_median_minutes=dev_review_median_minutes,
        release_wait_median_minutes=release_wait_median_minutes,
        change_failure_rate=change_failure_rate,
        mttr_minutes=mttr_minutes,
        mttr_alpha_minutes=mttr_alpha_minutes,
        lead_post_production_median_minutes=lead_post_production_median_minutes,
        lead_time_sample_count=lt_sample,
        lead_time_match_counts=lt_counts,
    )


def calculate_deployment_frequency_per_week(
    session: Session,
    *,
    start_dt: datetime,
    end_dt: datetime,
    repository_id: int,
) -> Decimal:
    total_releases = (
        session.execute(
            select(func.count(Release.id)).where(
                Release.repository_id == repository_id,
                Release.customer_release.is_(True),
                Release.committed_at >= start_dt,
                Release.committed_at < end_dt,
            )
        )
        .scalars()
        .one()
    )
    weeks = Decimal((end_dt - start_dt).total_seconds()) / Decimal(604800)
    if weeks == 0:
        return Decimal("0")
    return (Decimal(total_releases) / weeks).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def calculate_lead_time_minutes(
    session: Session,
    *,
    start_dt: datetime,
    end_dt: datetime,
    repository_id: int,
    config: ConfigurationSchema | None = None,
) -> int | None:
    filters = _lead_time_mr_filters(
        start_dt=start_dt,
        end_dt=end_dt,
        repository_id=repository_id,
        config=config or ConfigurationSchema(),
    )
    return _median_minutes_from_hours(
        session.execute(
            select(MergeRequest.lead_time_hours).where(
                MergeRequest.lead_time_hours.is_not(None),
                *filters,
            )
        )
        .scalars()
        .all()
    )


def calculate_lead_time_diagnostics(
    session: Session,
    *,
    start_dt: datetime,
    end_dt: datetime,
    repository_id: int,
    config: ConfigurationSchema | None = None,
) -> tuple[int, dict[str, int]]:
    """MR counts in the lead-time window.

    Sample used for median plus status breakdown (all rows with tag date).
    """
    filters = _lead_time_mr_filters(
        start_dt=start_dt,
        end_dt=end_dt,
        repository_id=repository_id,
        config=config or ConfigurationSchema(),
    )
    sample = int(
        session.execute(
            select(func.count(MergeRequest.id)).where(
                MergeRequest.lead_time_hours.is_not(None),
                *filters,
            )
        ).scalar_one()
    )
    rows = session.execute(
        select(MergeRequest.lead_time_match_status, func.count(MergeRequest.id)).where(
            *filters,
        ).group_by(MergeRequest.lead_time_match_status)
    ).all()
    counts: dict[str, int] = {}
    for status, cnt in rows:
        key = str(status).strip() if status is not None else "unknown"
        counts[key] = int(cnt)
    return sample, counts


def calculate_release_wait_minutes(
    session: Session,
    *,
    start_dt: datetime,
    end_dt: datetime,
    repository_id: int,
    config: ConfigurationSchema | None = None,
) -> int | None:
    filters = _lead_time_mr_filters(
        start_dt=start_dt,
        end_dt=end_dt,
        repository_id=repository_id,
        config=config or ConfigurationSchema(),
    )
    return _median_minutes_from_hours(
        session.execute(
            select(MergeRequest.release_wait_time_hours).where(
                MergeRequest.release_wait_time_hours.is_not(None),
                *filters,
            )
        )
        .scalars()
        .all()
    )


def calculate_dev_review_minutes(
    session: Session,
    *,
    start_dt: datetime,
    end_dt: datetime,
    repository_id: int,
    config: ConfigurationSchema | None = None,
) -> int | None:
    filters = _lead_time_mr_filters(
        start_dt=start_dt,
        end_dt=end_dt,
        repository_id=repository_id,
        config=config or ConfigurationSchema(),
    )
    rows = session.execute(
        select(MergeRequest.lead_time_hours, MergeRequest.release_wait_time_hours).where(
            MergeRequest.lead_time_hours.is_not(None),
            MergeRequest.release_wait_time_hours.is_not(None),
            *filters,
        )
    ).all()
    if not rows:
        return None
    dev_review_minutes: list[float] = []
    for lead_time_hours, release_wait_hours in rows:
        if lead_time_hours is None or release_wait_hours is None:
            continue
        delta_hours = float(lead_time_hours) - float(release_wait_hours)
        if delta_hours >= 0:
            dev_review_minutes.append(delta_hours * 60.0)
    if not dev_review_minutes:
        return None
    return int(Decimal(str(median(dev_review_minutes))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _lead_time_mr_exclusion_clauses(
    config: ConfigurationSchema,
) -> list[object] | None:
    """OR of release-only title/source markers, or None when no exclusions apply."""
    if not config.gitlab.exclude_release_only_mrs_from_lead_time:
        return None
    title_markers = [
        marker.strip().lower()
        for marker in config.gitlab.release_mr_title_markers
        if marker.strip()
    ]
    source_markers = [
        marker.strip().lower()
        for marker in config.gitlab.release_mr_source_branch_markers
        if marker.strip()
    ]
    exclusion_clauses: list[object] = []
    for marker in title_markers:
        exclusion_clauses.append(
            func.lower(func.coalesce(MergeRequest.title, "")).like(f"%{marker}%")
        )
    for marker in source_markers:
        exclusion_clauses.append(
            func.lower(func.coalesce(MergeRequest.source_branch, "")).like(f"%{marker}%")
        )
    return exclusion_clauses or None


def _lead_time_mr_filters_core(
    *,
    start_dt: datetime,
    end_dt: datetime,
    repository_id_column,
    config: ConfigurationSchema,
) -> list[object]:
    filters: list[object] = [
        repository_id_column,
        MergeRequest.first_customer_tag_date.is_not(None),
        MergeRequest.first_customer_tag_date >= start_dt,
        MergeRequest.first_customer_tag_date < end_dt,
    ]

    ex = _lead_time_mr_exclusion_clauses(config)
    if ex is not None:
        filters.append(~or_(*ex))
    return filters


def _lead_time_mr_filters(
    *,
    start_dt: datetime,
    end_dt: datetime,
    repository_id: int,
    config: ConfigurationSchema,
) -> list[object]:
    return _lead_time_mr_filters_core(
        start_dt=start_dt,
        end_dt=end_dt,
        repository_id_column=MergeRequest.repository_id == repository_id,
        config=config,
    )


def _lead_time_mr_filters_for_repos(
    *,
    start_dt: datetime,
    end_dt: datetime,
    repository_ids: list[int],
    config: ConfigurationSchema,
) -> list[object]:
    if not repository_ids:
        return _lead_time_mr_filters_core(
            start_dt=start_dt,
            end_dt=end_dt,
            repository_id_column=MergeRequest.repository_id == -1,
            config=config,
        )
    if len(repository_ids) == 1:
        return _lead_time_mr_filters_core(
            start_dt=start_dt,
            end_dt=end_dt,
            repository_id_column=MergeRequest.repository_id == repository_ids[0],
            config=config,
        )
    return _lead_time_mr_filters_core(
        start_dt=start_dt,
        end_dt=end_dt,
        repository_id_column=MergeRequest.repository_id.in_(repository_ids),
        config=config,
    )


def merge_request_included_in_lead_time_cohort(
    *,
    title: str | None,
    source_branch: str | None,
    first_customer_tag_date: datetime | None,
    config: ConfigurationSchema,
) -> bool:
    """True when an MR would pass `_lead_time_mr_filters` except period/repository (same exclusion rules)."""
    if first_customer_tag_date is None:
        return False
    if not config.gitlab.exclude_release_only_mrs_from_lead_time:
        return True
    t = (title or "").lower()
    src = (source_branch or "").lower()
    for marker in config.gitlab.release_mr_title_markers:
        m = marker.strip().lower()
        if m and m in t:
            return False
    for marker in config.gitlab.release_mr_source_branch_markers:
        m = marker.strip().lower()
        if m and m in src:
            return False
    return True


def calculate_change_failure_rate(
    session: Session,
    *,
    start_dt: datetime,
    end_dt: datetime,
    repository_id: int,
) -> Decimal:
    eligible_release_ids = (
        session.execute(
            select(Release.id).where(
                Release.repository_id == repository_id,
                Release.customer_release.is_(True),
                Release.committed_at >= start_dt,
                Release.committed_at < end_dt,
            )
        )
        .scalars()
        .all()
    )
    if not eligible_release_ids:
        return Decimal("0")

    failed_count = (
        session.execute(
            select(func.count(distinct(BugRelease.release_id)))
            .join(ProductionBug, ProductionBug.id == BugRelease.bug_id)
            .where(
                BugRelease.release_id.in_(eligible_release_ids),
                cfr_eligible_production_bug_predicate(),
            )
        )
        .scalars()
        .one()
    )
    return (Decimal(failed_count) / Decimal(len(eligible_release_ids))).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )


def calculate_mttr_minutes(
    session: Session,
    *,
    start_dt: datetime,
    end_dt: datetime,
) -> int | None:
    values = (
        session.execute(
            select(ProductionBug.mttr_minutes).where(
                ProductionBug.healthy.is_(True),
                ProductionBug.jira_created_at_valid.is_(True),
                ProductionBug.closed_at.is_not(None),
                ProductionBug.closed_at >= start_dt,
                ProductionBug.closed_at < end_dt,
                ProductionBug.mttr_minutes.is_not(None),
            )
        )
        .scalars()
        .all()
    )
    return _median_minutes(values)


def calculate_mttr_alpha_minutes(
    session: Session,
    *,
    start_dt: datetime,
    end_dt: datetime,
) -> int | None:
    values = (
        session.execute(
            select(ProductionBug.mttr_alpha_minutes).where(
                ProductionBug.healthy.is_(True),
                ProductionBug.jira_created_at_valid.is_(True),
                ProductionBug.created_at.isnot(None),
                ProductionBug.first_fix_release_date.is_not(None),
                ProductionBug.first_fix_release_date >= start_dt,
                ProductionBug.first_fix_release_date < end_dt,
                ProductionBug.mttr_alpha_minutes.is_not(None),
            )
        )
        .scalars()
        .all()
    )
    return _median_minutes(values)


def calculate_lead_post_production_minutes(
    session: Session,
    *,
    start_dt: datetime,
    end_dt: datetime,
    repository_id: int,
) -> int | None:
    return _median_minutes_from_hours(
        session.execute(
            select(MergeRequest.lead_post_production_hours).where(
                MergeRequest.repository_id == repository_id,
                MergeRequest.first_customer_tag_date.is_not(None),
                MergeRequest.first_customer_tag_date >= start_dt,
                MergeRequest.first_customer_tag_date < end_dt,
                MergeRequest.lead_post_production_hours.is_not(None),
            )
        )
        .scalars()
        .all()
    )


def _period_datetimes(period_start: date, period_end: date) -> tuple[datetime, datetime]:
    """Return [start, end) UTC bounds for metric queries (exclusive end)."""
    start_dt = datetime.combine(period_start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(period_end + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start_dt, end_dt


def period_metric_bounds(period_start: date, period_end: date) -> tuple[datetime, datetime]:
    """Public alias for snapshot and other callers (same semantics as _period_datetimes)."""
    return _period_datetimes(period_start, period_end)


def _median_minutes_from_hours(values: list[Decimal | None]) -> int | None:
    filtered = [float(value) * 60.0 for value in values if value is not None]
    if not filtered:
        return None
    return int(Decimal(str(median(filtered))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _median_minutes(values: list[int | None]) -> int | None:
    filtered = [value for value in values if value is not None]
    if not filtered:
        return None
    return int(Decimal(str(median(filtered))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _deployment_level(value: float) -> str:
    if value > 7:
        return "ELITE"
    if value >= 1:
        return "HIGH"
    if value >= (1 / 4):
        return "MEDIUM"
    return "LOW"


def _lead_time_level(value_minutes: int) -> str:
    if value_minutes < 60:
        return "ELITE"
    if value_minutes < 7 * 24 * 60:
        return "HIGH"
    if value_minutes < 30 * 24 * 60:
        return "MEDIUM"
    return "LOW"


def _cfr_level(value: float) -> str:
    if value < 0.05:
        return "ELITE"
    if value <= 0.10:
        return "HIGH"
    if value <= 0.15:
        return "MEDIUM"
    return "LOW"


def _mttr_level(value_minutes: int) -> str:
    if value_minutes < 60:
        return "ELITE"
    if value_minutes < 24 * 60:
        return "HIGH"
    if value_minutes <= 7 * 24 * 60:
        return "MEDIUM"
    return "LOW"
