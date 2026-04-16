from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.metric_snapshot import MetricSnapshot
from app.schemas.metrics import (
    CurrentMetricsResponse,
    HistoryDataPoint,
    HistoryResponse,
    LeadTimeDiagnostics,
    MetricValue,
    Pagination,
    PerformanceLevel,
    PerformanceLevels,
    PeriodType,
    Trend,
)
from app.services.metric_service import classify_performance_level


def _mean_float_from_decimal(values: list[Decimal | None]) -> float | None:
    xs = [float(v) for v in values if v is not None]
    if not xs:
        return None
    return sum(xs) / len(xs)


def _median_int(values: list[int | None]) -> int | None:
    xs = [v for v in values if v is not None]
    if not xs:
        return None
    return int(median(xs))


def _minutes_display(minutes: int | None) -> str | None:
    if minutes is None:
        return None
    if minutes < 60:
        return f"{minutes} min"
    if minutes < 24 * 60:
        h = minutes // 60
        return f"{h} hour" + ("s" if h != 1 else "")
    d = minutes // (24 * 60)
    return f"{d} day" + ("s" if d != 1 else "")


def _cfr_display(ratio: float | None) -> str | None:
    if ratio is None:
        return None
    return f"{ratio * 100:.0f}%"


def _trend_for_values(cur: float | None, prev: float | None) -> tuple[Trend | None, float | None]:
    if cur is None or prev is None:
        return None, None
    if prev == 0:
        if cur == 0:
            return Trend.STABLE, 0.0
        return Trend.UP, 100.0
    pct = (cur - prev) / abs(prev) * 100.0
    if abs(pct) < 0.05:
        return Trend.STABLE, round(pct, 1)
    return (Trend.UP if pct > 0 else Trend.DOWN), round(pct, 1)


def _level_for_row(
    *,
    dep: float | None,
    lead: int | None,
    cfr: float | None,
    mttr_alpha: int | None,
) -> PerformanceLevels:
    overall = classify_performance_level(
        deployment_freq_per_week=dep,
        lead_time_minutes=lead,
        change_failure_rate=cfr,
        mttr_minutes=mttr_alpha,
    )
    ov = PerformanceLevel(overall) if overall else None
    d_level = PerformanceLevel(_deployment_level_only(dep)) if dep is not None else None
    l_level = PerformanceLevel(_lead_level_only(lead)) if lead is not None else None
    c_level = PerformanceLevel(_cfr_level_only(cfr)) if cfr is not None else None
    m_level = PerformanceLevel(_mttr_level_only(mttr_alpha)) if mttr_alpha is not None else None
    return PerformanceLevels(
        overall=ov,
        deployment_frequency=d_level,
        lead_time=l_level,
        change_failure_rate=c_level,
        mttr=m_level,
    )


def _deployment_level_only(value: float) -> str:
    if value > 7:
        return "ELITE"
    if value >= 1:
        return "HIGH"
    if value >= (1 / 4):
        return "MEDIUM"
    return "LOW"


def _lead_level_only(value_minutes: int) -> str:
    if value_minutes < 60:
        return "ELITE"
    if value_minutes < 7 * 24 * 60:
        return "HIGH"
    if value_minutes < 30 * 24 * 60:
        return "MEDIUM"
    return "LOW"


def _cfr_level_only(value: float) -> str:
    if value < 0.05:
        return "ELITE"
    if value <= 0.10:
        return "HIGH"
    if value <= 0.15:
        return "MEDIUM"
    return "LOW"


def _mttr_level_only(value_minutes: int) -> str:
    if value_minutes < 60:
        return "ELITE"
    if value_minutes < 24 * 60:
        return "HIGH"
    if value_minutes <= 7 * 24 * 60:
        return "MEDIUM"
    return "LOW"


@dataclass(frozen=True)
class _Window:
    period_start: date
    period_end: date


def _last_day_of_month(d: date) -> date:
    if d.month == 12:
        first_next = date(d.year + 1, 1, 1)
    else:
        first_next = date(d.year, d.month + 1, 1)
    return first_next - timedelta(days=1)


def _previous_window(w: _Window, period_type: str) -> _Window:
    """Calendar-aligned previous period (used by tests and trend baseline)."""
    pt = period_type.upper()
    if pt == "WEEK":
        return _Window(
            w.period_start - timedelta(days=7),
            w.period_end - timedelta(days=7),
        )
    if pt == "MONTH":
        y, m = w.period_start.year, w.period_start.month
        if m == 1:
            y, m = y - 1, 12
        else:
            m -= 1
        start = date(y, m, 1)
        return _Window(start, _last_day_of_month(start))
    if pt == "QUARTER":
        sm = w.period_start.month
        sy = w.period_start.year
        if sm == 1:
            return _Window(date(sy - 1, 10, 1), date(sy - 1, 12, 31))
        if sm == 4:
            return _Window(date(sy, 1, 1), date(sy, 3, 31))
        if sm == 7:
            return _Window(date(sy, 4, 1), date(sy, 6, 30))
        if sm == 10:
            return _Window(date(sy, 7, 1), date(sy, 9, 30))
        raise ValueError(f"Unsupported quarter window start month: {sm}")
    raise ValueError(f"Unsupported period_type for _previous_window: {period_type!r}")


def _latest_window(
    db: Session, *, period_type: str, repository_id: int | None
) -> _Window | None:
    recent = _recent_windows(
        db, period_type=period_type, repository_id=repository_id, limit=1
    )
    return recent[0] if recent else None


def _recent_windows(
    db: Session,
    *,
    period_type: str,
    repository_id: int | None,
    limit: int,
) -> list[_Window]:
    today = datetime.now(timezone.utc).date()
    q = (
        select(MetricSnapshot.period_start, MetricSnapshot.period_end)
        .where(
            MetricSnapshot.period_type == period_type,
            MetricSnapshot.period_end <= today,
        )
        .distinct()
        .order_by(MetricSnapshot.period_end.desc())
    )
    if repository_id is not None:
        q = q.where(MetricSnapshot.repository_id == repository_id)
    
    results = db.execute(q.limit(limit)).all()
    if not results:
        fallback_q = (
            select(MetricSnapshot.period_start, MetricSnapshot.period_end)
            .where(MetricSnapshot.period_type == period_type)
            .distinct()
            .order_by(MetricSnapshot.period_end.desc())
        )
        if repository_id is not None:
            fallback_q = fallback_q.where(MetricSnapshot.repository_id == repository_id)
        results = db.execute(fallback_q.limit(limit)).all()
        
    return [_Window(period_start=r[0], period_end=r[1]) for r in results]


def _load_snapshots_for_windows(
    db: Session,
    *,
    period_type: str,
    windows: list[_Window],
    repository_id: int | None,
) -> list[MetricSnapshot]:
    if not windows:
        return []
    
    from sqlalchemy import or_
    conditions = [
        (MetricSnapshot.period_start == w.period_start) & (MetricSnapshot.period_end == w.period_end)
        for w in windows
    ]
    
    q = select(MetricSnapshot).where(
        MetricSnapshot.period_type == period_type,
        MetricSnapshot.repository_id.isnot(None),
        or_(*conditions)
    )
    if repository_id is not None:
        q = q.where(MetricSnapshot.repository_id == repository_id)
    return list(db.execute(q).scalars().all())


def _merge_lead_time_match_counts(rows: list[MetricSnapshot]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for r in rows:
        raw = r.lead_time_match_counts
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
        if not isinstance(raw, dict):
            continue
        for k, v in raw.items():
            if isinstance(v, bool):
                continue
            if isinstance(v, int):
                merged[str(k)] = merged.get(str(k), 0) + v
            elif isinstance(v, float) and v == int(v):
                merged[str(k)] = merged.get(str(k), 0) + int(v)
    return merged


def _aggregate_rows(rows: list[MetricSnapshot]) -> dict[str, float | int | None | dict[str, int]]:
    dep = _mean_float_from_decimal([r.deployment_freq for r in rows])
    lead = _median_int([r.lead_time_minutes for r in rows])
    rw = _median_int([r.release_wait_median_minutes for r in rows])
    cfr = _mean_float_from_decimal([r.change_failure_rate for r in rows])
    mttr_alpha = _median_int([r.mttr_alpha_minutes for r in rows])
    lt_samples = sum(int(r.lead_time_sample_count or 0) for r in rows)
    lt_counts = _merge_lead_time_match_counts(rows)
    return {
        "deployment_freq": dep,
        "lead_time_minutes": lead,
        "release_wait_median_minutes": rw,
        "change_failure_rate": cfr,
        "mttr_alpha_minutes": mttr_alpha,
        "lead_time_sample_count": lt_samples,
        "lead_time_match_counts": lt_counts,
    }


def _max_generated_at(rows: list[MetricSnapshot]) -> datetime:
    times = [r.created_at for r in rows if r.created_at is not None]
    if not times:
        return datetime.now(timezone.utc)
    return max(times)


def build_current_metrics_response(
    db: Session,
    *,
    repository_id: int | None = None,
    period_type: str = "WEEK",
) -> CurrentMetricsResponse:
    # Latest snapshot window vs the immediately prior window (repo rows aggregated per window).
    recent = _recent_windows(
        db,
        period_type=period_type,
        repository_id=repository_id,
        limit=2,
    )

    if not recent:
        today = datetime.now(timezone.utc).date()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        now = datetime.now(timezone.utc)
        z = MetricValue(value=None, unit="DEPLOYMENTS_PER_WEEK", display_value=None)
        m = MetricValue(value=None, unit="MINUTES", display_value=None)
        r = MetricValue(value=None, unit="RATIO", display_value=None)
        return CurrentMetricsResponse(
            deployment_frequency=z,
            lead_time=m,
            change_failure_rate=r,
            mttr=m,
            overall_performance_level=None,
            period_start=monday,
            period_end=sunday,
            repository_count=0,
            generated_at=now,
            mttr_alpha=None,
            release_wait_time=None,
            lead_time_diagnostics=None,
        )

    current_windows = [recent[0]]
    prev_windows = [recent[1]] if len(recent) > 1 else []

    rows = _load_snapshots_for_windows(
        db,
        period_type=period_type,
        windows=current_windows,
        repository_id=repository_id,
    )
    prev_rows = _load_snapshots_for_windows(
        db,
        period_type=period_type,
        windows=prev_windows,
        repository_id=repository_id,
    )

    cur = _aggregate_rows(rows)
    prev = _aggregate_rows(prev_rows)

    combined_start = min(w.period_start for w in current_windows)
    combined_end = max(w.period_end for w in current_windows)

    dep = cur["deployment_freq"]
    dep_p = prev["deployment_freq"]
    lead = cur["lead_time_minutes"]
    lead_p = prev["lead_time_minutes"]
    cfr = cur["change_failure_rate"]
    cfr_p = prev["change_failure_rate"]
    mttr_a = cur["mttr_alpha_minutes"]
    mttr_p = prev["mttr_alpha_minutes"]
    rw = cur["release_wait_median_minutes"]
    rw_p = prev["release_wait_median_minutes"]

    t_dep, p_dep = _trend_for_values(dep, dep_p)
    t_lead, p_lead = _trend_for_values(
        float(lead) if lead is not None else None,
        float(lead_p) if lead_p is not None else None,
    )
    t_cfr, p_cfr = _trend_for_values(cfr, cfr_p)
    t_mttr, p_mttr = _trend_for_values(
        float(mttr_a) if mttr_a is not None else None,
        float(mttr_p) if mttr_p is not None else None,
    )
    t_rw, p_rw = _trend_for_values(
        float(rw) if rw is not None else None,
        float(rw_p) if rw_p is not None else None,
    )

    overall_raw = classify_performance_level(
        deployment_freq_per_week=dep,
        lead_time_minutes=lead,
        change_failure_rate=cfr,
        mttr_minutes=mttr_a,
    )
    overall_pl = PerformanceLevel(overall_raw) if overall_raw else None

    dep_level = (
        PerformanceLevel(_deployment_level_only(dep))
        if dep is not None
        else None
    )
    lead_level = (
        PerformanceLevel(_lead_level_only(lead))
        if lead is not None
        else None
    )
    cfr_level = (
        PerformanceLevel(_cfr_level_only(cfr))
        if cfr is not None
        else None
    )
    mttr_level = (
        PerformanceLevel(_mttr_level_only(mttr_a))
        if mttr_a is not None
        else None
    )

    repo_count = len({r.repository_id for r in rows if r.repository_id is not None})
    if repository_id is not None:
        repo_count = 1 if rows else 0

    gen_at = _max_generated_at(rows)

    lt_counts_raw = cur.get("lead_time_match_counts")
    lt_match_counts: dict[str, int] = (
        dict(lt_counts_raw) if isinstance(lt_counts_raw, dict) else {}
    )
    lead_diag = LeadTimeDiagnostics(
        sample_count=int(cur.get("lead_time_sample_count") or 0),
        match_counts=lt_match_counts,
    )

    return CurrentMetricsResponse(
        deployment_frequency=MetricValue(
            value=dep,
            unit="DEPLOYMENTS_PER_WEEK",
            display_value=f"{dep:.2f}/week" if dep is not None else None,
            trend=t_dep,
            trend_percentage=p_dep,
            performance_level=dep_level,
        ),
        lead_time=MetricValue(
            value=float(lead) if lead is not None else None,
            unit="MINUTES",
            display_value=_minutes_display(lead),
            trend=t_lead,
            trend_percentage=p_lead,
            performance_level=lead_level,
        ),
        change_failure_rate=MetricValue(
            value=cfr,
            unit="RATIO",
            display_value=_cfr_display(cfr),
            trend=t_cfr,
            trend_percentage=p_cfr,
            performance_level=cfr_level,
        ),
        mttr=MetricValue(
            value=float(mttr_a) if mttr_a is not None else None,
            unit="MINUTES",
            display_value=_minutes_display(mttr_a),
            trend=t_mttr,
            trend_percentage=p_mttr,
            performance_level=mttr_level,
        ),
        overall_performance_level=overall_pl,
        period_start=combined_start,
        period_end=combined_end,
        repository_count=repo_count,
        generated_at=gen_at,
        mttr_alpha=MetricValue(
            value=float(mttr_a) if mttr_a is not None else None,
            unit="MINUTES",
            display_value=_minutes_display(mttr_a),
            trend=t_mttr,
            trend_percentage=p_mttr,
            performance_level=mttr_level,
        ),
        release_wait_time=MetricValue(
            value=float(rw) if rw is not None else None,
            unit="MINUTES",
            display_value=_minutes_display(rw),
            trend=t_rw,
            trend_percentage=p_rw,
            performance_level=(
                PerformanceLevel(_lead_level_only(rw))
                if rw is not None
                else None
            ),
        ),
        lead_time_diagnostics=lead_diag,
    )


def build_history_response(
    db: Session,
    *,
    period_type: PeriodType,
    from_date: date,
    to_date: date,
    repository_id: int | None,
    page: int,
    size: int,
) -> HistoryResponse:
    size = max(1, min(size, 100))
    page = max(0, page)

    q = (
        select(MetricSnapshot.period_start, MetricSnapshot.period_end)
        .where(
            MetricSnapshot.period_type == period_type.value,
            MetricSnapshot.period_end >= from_date,
            MetricSnapshot.period_start <= to_date,
            MetricSnapshot.repository_id.isnot(None),
        )
        .distinct()
        .order_by(MetricSnapshot.period_start.desc())
    )
    if repository_id is not None:
        q = q.where(MetricSnapshot.repository_id == repository_id)

    all_periods = list(db.execute(q).all())
    total_elements = len(all_periods)
    total_pages = (total_elements + size - 1) // size if total_elements else 0
    slice_ = all_periods[page * size : page * size + size]

    data: list[HistoryDataPoint] = []
    for period_start, period_end in slice_:
        w = _Window(period_start=period_start, period_end=period_end)
        rows = _load_snapshots_for_windows(
            db,
            period_type=period_type.value,
            windows=[w],
            repository_id=repository_id,
        )
        agg = _aggregate_rows(rows)
        dep = agg["deployment_freq"]
        lead = agg["lead_time_minutes"]
        cfr = agg["change_failure_rate"]
        mttr_alpha = agg["mttr_alpha_minutes"]
        rw = agg["release_wait_median_minutes"]
        levels = _level_for_row(
            dep=dep,
            lead=lead,
            cfr=cfr,
            mttr_alpha=mttr_alpha,
        )
        lt_sc = int(agg.get("lead_time_sample_count") or 0) if agg else 0
        data.append(
            HistoryDataPoint(
                period_start=period_start,
                period_end=period_end,
                deployment_frequency=dep,
                lead_time_minutes=lead,
                lead_time_sample_count=lt_sc,
                change_failure_rate=cfr,
                mttr_minutes=mttr_alpha,
                mttr_alpha_minutes=mttr_alpha,
                release_wait_median_minutes=rw,
                performance_level=levels,
            )
        )

    return HistoryResponse(
        period_type=period_type,
        from_date=from_date,
        to_date=to_date,
        repository_id=repository_id,
        data=data,
        pagination=Pagination(
            page=page,
            size=size,
            total_elements=total_elements,
            total_pages=total_pages,
            has_next=(page + 1) * size < total_elements,
            has_previous=page > 0,
        ),
    )
