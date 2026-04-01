from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP
from statistics import median

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.models.bug_release import BugRelease
from app.models.merge_request import MergeRequest
from app.models.production_bug import ProductionBug
from app.models.release import Release

PERIOD_TYPES = ("WEEK", "MONTH", "QUARTER")
PERFORMANCE_LEVELS = ("LOW", "MEDIUM", "HIGH", "ELITE")


@dataclass(frozen=True)
class MetricValues:
    deployment_freq: Decimal
    lead_time_minutes: int | None
    release_wait_median_minutes: int | None
    change_failure_rate: Decimal
    mttr_alpha_minutes: int | None
    lead_post_production_median_minutes: int | None


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
) -> MetricValues:
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
    )
    release_wait_median_minutes = calculate_release_wait_minutes(
        session,
        start_dt=start_dt,
        end_dt=end_dt,
        repository_id=repository_id,
    )
    change_failure_rate = calculate_change_failure_rate(
        session,
        start_dt=start_dt,
        end_dt=end_dt,
        repository_id=repository_id,
    )
    mttr_alpha_minutes = calculate_mttr_alpha_minutes(
        session,
        start_dt=start_dt,
        end_dt=end_dt,
    )
    lead_post_production_median_minutes = calculate_lead_post_production_minutes(
        session,
        start_dt=start_dt,
        end_dt=end_dt,
        repository_id=repository_id,
    )
    return MetricValues(
        deployment_freq=deployment_freq,
        lead_time_minutes=lead_time_minutes,
        release_wait_median_minutes=release_wait_median_minutes,
        change_failure_rate=change_failure_rate,
        mttr_alpha_minutes=mttr_alpha_minutes,
        lead_post_production_median_minutes=lead_post_production_median_minutes,
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
) -> int | None:
    return _median_minutes_from_hours(
        session.execute(
            select(MergeRequest.lead_time_hours).where(
                MergeRequest.repository_id == repository_id,
                MergeRequest.first_customer_tag_date.is_not(None),
                MergeRequest.first_customer_tag_date >= start_dt,
                MergeRequest.first_customer_tag_date < end_dt,
                MergeRequest.lead_time_hours.is_not(None),
            )
        )
        .scalars()
        .all()
    )


def calculate_release_wait_minutes(
    session: Session,
    *,
    start_dt: datetime,
    end_dt: datetime,
    repository_id: int,
) -> int | None:
    return _median_minutes_from_hours(
        session.execute(
            select(MergeRequest.release_wait_time_hours).where(
                MergeRequest.repository_id == repository_id,
                MergeRequest.first_customer_tag_date.is_not(None),
                MergeRequest.first_customer_tag_date >= start_dt,
                MergeRequest.first_customer_tag_date < end_dt,
                MergeRequest.release_wait_time_hours.is_not(None),
            )
        )
        .scalars()
        .all()
    )


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
                ProductionBug.healthy.is_(True),
            )
        )
        .scalars()
        .one()
    )
    return (Decimal(failed_count) / Decimal(len(eligible_release_ids))).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )


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
    start_dt = datetime.combine(period_start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(period_end, time.max, tzinfo=timezone.utc)
    return start_dt, end_dt + (datetime.resolution)


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
