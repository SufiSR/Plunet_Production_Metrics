from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config_schema import ConfigurationSchema
from app.models.metric_snapshot import MetricSnapshot
from app.models.repository import Repository
from app.services.metric_service import (
    PERIOD_TYPES,
    calculate_mttr_alpha_minutes,
    calculate_mttr_minutes,
    calculate_period_metrics,
    period_metric_bounds,
)


@dataclass(frozen=True)
class PeriodWindow:
    period_type: str
    period_start: date
    period_end: date


def refresh_snapshots(
    session: Session,
    *,
    config: ConfigurationSchema,
    now: datetime | None = None,
) -> int:
    ref_now = now or datetime.now(timezone.utc)
    start_date = (ref_now - timedelta(days=config.backend.lookback_days)).date()
    end_date = ref_now.date()
    repositories = (
        session.execute(select(Repository.id).where(Repository.active.is_(True))).scalars().all()
    )
    if not repositories:
        return 0

    windows: list[PeriodWindow] = []
    for period_type in PERIOD_TYPES:
        windows.extend(
            _build_period_windows(
                period_type=period_type, start_date=start_date, end_date=end_date,
            )
        )

    mttr_by_window: dict[tuple[date, date], int | None] = {}
    mttr_resolution_by_window: dict[tuple[date, date], int | None] = {}
    for window in windows:
        wk = (window.period_start, window.period_end)
        if wk not in mttr_by_window:
            start_dt, end_dt = period_metric_bounds(window.period_start, window.period_end)
            mttr_by_window[wk] = calculate_mttr_alpha_minutes(
                session, start_dt=start_dt, end_dt=end_dt
            )
            mttr_resolution_by_window[wk] = calculate_mttr_minutes(
                session, start_dt=start_dt, end_dt=end_dt
            )

    written = 0
    for repository_id in repositories:
        for window in windows:
            wk = (window.period_start, window.period_end)
            values = calculate_period_metrics(
                session,
                period_start=window.period_start,
                period_end=window.period_end,
                repository_id=repository_id,
                mttr_minutes_override=mttr_resolution_by_window[wk],
                mttr_alpha_minutes_override=mttr_by_window[wk],
            )
            session.execute(
                delete(MetricSnapshot).where(
                    MetricSnapshot.repository_id == repository_id,
                    MetricSnapshot.period_type == window.period_type,
                    MetricSnapshot.period_start == window.period_start,
                )
            )
            session.add(
                MetricSnapshot(
                    repository_id=repository_id,
                    period_start=window.period_start,
                    period_end=window.period_end,
                    period_type=window.period_type,
                    deployment_freq=values.deployment_freq,
                    lead_time_minutes=values.lead_time_minutes,
                    release_wait_median_minutes=values.release_wait_median_minutes,
                    change_failure_rate=values.change_failure_rate,
                    mttr_minutes=values.mttr_minutes,
                    mttr_alpha_minutes=values.mttr_alpha_minutes,
                    lead_post_production_median_minutes=values.lead_post_production_median_minutes,
                    lead_time_sample_count=values.lead_time_sample_count,
                    lead_time_match_counts=values.lead_time_match_counts or None,
                )
            )
            written += 1
    session.commit()
    return written


def _build_period_windows(
    *,
    period_type: str,
    start_date: date,
    end_date: date,
) -> list[PeriodWindow]:
    windows: list[PeriodWindow] = []
    cursor = _period_start(period_type, start_date)
    while cursor <= end_date:
        period_start = cursor
        period_end = _period_end(period_type, period_start)
        windows.append(
            PeriodWindow(
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
            )
        )
        cursor = _next_period_start(period_type, period_start)
    return windows


def _period_start(period_type: str, value: date) -> date:
    if period_type == "WEEK":
        return value - timedelta(days=value.weekday())
    if period_type == "MONTH":
        return date(value.year, value.month, 1)
    if period_type == "QUARTER":
        quarter_month = ((value.month - 1) // 3) * 3 + 1
        return date(value.year, quarter_month, 1)
    raise ValueError(f"Unsupported period type: {period_type}")


def _period_end(period_type: str, period_start: date) -> date:
    if period_type == "WEEK":
        return period_start + timedelta(days=6)
    if period_type == "MONTH":
        next_month = _next_month(period_start)
        return next_month - timedelta(days=1)
    if period_type == "QUARTER":
        month = period_start.month
        year = period_start.year
        end_month = month + 2
        first_next = _next_month(date(year, end_month, 1))
        return first_next - timedelta(days=1)
    raise ValueError(f"Unsupported period type: {period_type}")


def _next_period_start(period_type: str, period_start: date) -> date:
    if period_type == "WEEK":
        return period_start + timedelta(days=7)
    if period_type == "MONTH":
        return _next_month(period_start)
    if period_type == "QUARTER":
        value = period_start
        for _ in range(3):
            value = _next_month(value)
        return value
    raise ValueError(f"Unsupported period type: {period_type}")


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)
