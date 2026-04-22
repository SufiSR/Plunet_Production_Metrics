from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.models.metric_snapshot import MetricSnapshot
from app.models.repository import Repository
from app.schemas.metrics import PeriodType, Trend
from app.services import metrics_public_service as mps


def _utc_ts(year: int, month: int, day: int, h: int = 12) -> datetime:
    return datetime(year, month, day, h, 0, tzinfo=timezone.utc)


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)
    return maker()


def test_mean_float_from_decimal_empty_and_values() -> None:
    assert mps._mean_float_from_decimal([]) is None
    assert mps._mean_float_from_decimal([None, None]) is None
    assert mps._mean_float_from_decimal([Decimal("2"), Decimal("4")]) == 3.0


def test_median_int_empty_and_values() -> None:
    assert mps._median_int([]) is None
    assert mps._median_int([None, 10, None, 30]) == 20


def test_minutes_display_branches() -> None:
    assert mps._minutes_display(None) is None
    assert mps._minutes_display(30) == "30 min"
    assert mps._minutes_display(60) == "1 hour"
    assert mps._minutes_display(120) == "2 hours"
    assert mps._minutes_display(24 * 60) == "1 day"
    assert mps._minutes_display(2 * 24 * 60) == "2 days"


def test_cfr_display() -> None:
    assert mps._cfr_display(None) is None
    assert mps._cfr_display(0.115) == "12%"


def test_trend_for_values() -> None:
    assert mps._trend_for_values(None, 1.0) == (None, None)
    t, p = mps._trend_for_values(0.0, 0.0)
    assert t == Trend.STABLE and p == 0.0
    t, p = mps._trend_for_values(1.0, 0.0)
    assert t == Trend.UP and p == 100.0
    t, p = mps._trend_for_values(10.0, 20.0)
    assert t == Trend.DOWN and p == -50.0
    t, p = mps._trend_for_values(100.02, 100.0)
    assert t == Trend.STABLE


def test_deployment_lead_cfr_mttr_level_only_branches() -> None:
    assert mps._deployment_level_only(8.0) == "ELITE"
    assert mps._deployment_level_only(1.0) == "HIGH"
    assert mps._deployment_level_only(0.3) == "MEDIUM"
    assert mps._deployment_level_only(0.1) == "LOW"

    assert mps._lead_level_only(30) == "ELITE"
    assert mps._lead_level_only(3 * 24 * 60) == "HIGH"
    assert mps._lead_level_only(20 * 24 * 60) == "MEDIUM"
    assert mps._lead_level_only(40 * 24 * 60) == "LOW"

    assert mps._cfr_level_only(0.04) == "ELITE"
    assert mps._cfr_level_only(0.08) == "HIGH"
    assert mps._cfr_level_only(0.12) == "MEDIUM"
    assert mps._cfr_level_only(0.20) == "LOW"

    assert mps._mttr_level_only(30) == "ELITE"
    assert mps._mttr_level_only(2 * 60) == "HIGH"
    assert mps._mttr_level_only(5 * 24 * 60) == "MEDIUM"
    assert mps._mttr_level_only(10 * 24 * 60) == "LOW"


def test_level_for_row_builds_performance_levels() -> None:
    levels = mps._level_for_row(dep=2.0, lead=120, cfr=0.06, mttr_alpha=90)
    assert levels.overall is not None
    assert levels.deployment_frequency is not None
    assert levels.lead_time is not None
    assert levels.change_failure_rate is not None
    assert levels.mttr is not None


def test_previous_window_week_month_quarter() -> None:
    w = mps._Window(period_start=date(2026, 4, 7), period_end=date(2026, 4, 13))
    prev = mps._previous_window(w, "WEEK")
    assert prev.period_start == date(2026, 3, 31)
    assert prev.period_end == date(2026, 4, 6)

    jan = mps._Window(period_start=date(2026, 1, 1), period_end=date(2026, 1, 31))
    prev_m = mps._previous_window(jan, "MONTH")
    assert prev_m.period_start == date(2025, 12, 1)
    assert prev_m.period_end == date(2025, 12, 31)

    mar = mps._Window(period_start=date(2026, 3, 1), period_end=date(2026, 3, 31))
    prev_m2 = mps._previous_window(mar, "MONTH")
    assert prev_m2.period_start == date(2026, 2, 1)
    assert prev_m2.period_end == date(2026, 2, 28)

    q1 = mps._Window(period_start=date(2026, 1, 1), period_end=date(2026, 3, 31))
    prev_q = mps._previous_window(q1, "QUARTER")
    assert prev_q.period_start == date(2025, 10, 1)
    assert prev_q.period_end == date(2025, 12, 31)

    q3 = mps._Window(period_start=date(2026, 7, 1), period_end=date(2026, 9, 30))
    prev_q2 = mps._previous_window(q3, "QUARTER")
    assert prev_q2.period_start == date(2026, 4, 1)
    assert prev_q2.period_end == date(2026, 6, 30)


def test_latest_window_and_load_snapshots() -> None:
    with _session() as db:
        db.add(
            Repository(
                id=1,
                gitlab_id=1,
                name="a",
                path="g/a",
                default_branch="main",
                active=True,
            )
        )
        db.flush()
        db.add(
            MetricSnapshot(
                repository_id=1,
                period_type="WEEK",
                period_start=date(2026, 4, 7),
                period_end=date(2026, 4, 13),
                deployment_freq=Decimal("1.0"),
                lead_time_minutes=60,
                release_wait_median_minutes=30,
                change_failure_rate=Decimal("0.1"),
                mttr_minutes=None,
                mttr_alpha_minutes=45,
                lead_post_production_median_minutes=None,
                lead_time_sample_count=7,
                lead_time_match_counts={"matched": 5, "first_commit_missing": 2},
                created_at=_utc_ts(2026, 4, 13),
            )
        )
        db.commit()

        win = mps._latest_window(db, period_type="WEEK", repository_id=None)
        assert win is not None
        assert win.period_end == date(2026, 4, 13)

        rows = mps._load_snapshots_for_windows(
            db, period_type="WEEK", windows=[win], repository_id=None
        )
        assert len(rows) == 1
        agg = mps._aggregate_rows(rows)
        assert agg["deployment_freq"] == 1.0
        assert agg["lead_time_minutes"] == 60
        assert agg["lead_time_sample_count"] == 7
        assert agg["lead_time_match_counts"]["matched"] == 5
        assert agg["lead_time_match_counts"]["first_commit_missing"] == 2


def test_max_generated_at_uses_now_when_no_timestamps() -> None:
    class _Row:
        created_at = None

    out = mps._max_generated_at([_Row(), _Row()])
    assert out.tzinfo is not None


def test_build_current_metrics_response_no_snapshots() -> None:
    with _session() as db:
        resp = mps.build_current_metrics_response(db, repository_id=None, period_type="WEEK")
    assert resp.repository_count == 0
    assert resp.deployment_frequency.value is None


def test_build_current_metrics_response_with_week_trends_and_repo_filter() -> None:
    with _session() as db:
        for rid in (1, 2):
            db.add(
                Repository(
                    id=rid,
                    gitlab_id=rid,
                    name=f"r{rid}",
                    path=f"g/r{rid}",
                    default_branch="main",
                    active=True,
                )
            )
        db.flush()
        cur_start, cur_end = date(2026, 4, 7), date(2026, 4, 13)
        prev_start, prev_end = date(2026, 3, 31), date(2026, 4, 6)
        for rid in (1, 2):
            db.add(
                MetricSnapshot(
                    repository_id=rid,
                    period_type="WEEK",
                    period_start=cur_start,
                    period_end=cur_end,
                    deployment_freq=Decimal("2.0"),
                    lead_time_minutes=100,
                    release_wait_median_minutes=120,
                    change_failure_rate=Decimal("0.08"),
                    mttr_minutes=None,
                    mttr_alpha_minutes=200,
                    lead_post_production_median_minutes=None,
                    lead_time_sample_count=5,
                    lead_time_match_counts={"matched": 4, "first_commit_missing": 1},
                    created_at=_utc_ts(2026, 4, 13),
                )
            )
            db.add(
                MetricSnapshot(
                    repository_id=rid,
                    period_type="WEEK",
                    period_start=prev_start,
                    period_end=prev_end,
                    deployment_freq=Decimal("1.0"),
                    lead_time_minutes=200,
                    release_wait_median_minutes=60,
                    change_failure_rate=Decimal("0.12"),
                    mttr_minutes=None,
                    mttr_alpha_minutes=400,
                    lead_post_production_median_minutes=None,
                    created_at=_utc_ts(2026, 4, 6),
                )
            )
        db.commit()

        agg_all = mps.build_current_metrics_response(db, repository_id=None, period_type="WEEK")
        assert agg_all.repository_count == 2
        assert agg_all.deployment_frequency.value == 2.0
        assert agg_all.deployment_frequency.trend == Trend.UP
        assert agg_all.lead_time.value == 100.0
        assert agg_all.release_wait_time is not None
        assert agg_all.release_wait_time.value == 120.0
        assert agg_all.lead_time_diagnostics is not None
        assert agg_all.lead_time_diagnostics.sample_count >= 10
        assert agg_all.lead_time_diagnostics.match_counts.get("matched", 0) >= 8

        one = mps.build_current_metrics_response(db, repository_id=1, period_type="WEEK")
        assert one.repository_count == 1


def test_build_current_metrics_response_aggregates_trailing_quarters_for_yearly_view() -> None:
    with _session() as db:
        db.add(
            Repository(
                id=1,
                gitlab_id=1,
                name="r1",
                path="g/r1",
                default_branch="main",
                active=True,
            )
        )
        db.flush()
        # 8 quarters: 4 current-year window + 4 prior-year window.
        quarter_windows = [
            (date(2024, 4, 1), date(2024, 6, 30), Decimal("1.0"), 400),
            (date(2024, 7, 1), date(2024, 9, 30), Decimal("1.0"), 400),
            (date(2024, 10, 1), date(2024, 12, 31), Decimal("1.0"), 400),
            (date(2025, 1, 1), date(2025, 3, 31), Decimal("1.0"), 400),
            (date(2025, 4, 1), date(2025, 6, 30), Decimal("3.0"), 200),
            (date(2025, 7, 1), date(2025, 9, 30), Decimal("3.0"), 200),
            (date(2025, 10, 1), date(2025, 12, 31), Decimal("3.0"), 200),
            (date(2026, 1, 1), date(2026, 3, 31), Decimal("3.0"), 200),
        ]
        for idx, (p_start, p_end, dep, mttr) in enumerate(quarter_windows, start=1):
            db.add(
                MetricSnapshot(
                    repository_id=1,
                    period_type="QUARTER",
                    period_start=p_start,
                    period_end=p_end,
                    deployment_freq=dep,
                    lead_time_minutes=120,
                    release_wait_median_minutes=120,
                    change_failure_rate=Decimal("0.08"),
                    mttr_minutes=None,
                    mttr_alpha_minutes=mttr,
                    lead_post_production_median_minutes=None,
                    created_at=_utc_ts(2026, 4, min(idx, 28)),
                )
            )
        db.commit()

        yearly = mps.build_current_metrics_response(db, repository_id=1, period_type="QUARTER")
        assert yearly.period_start == date(2025, 4, 1)
        assert yearly.period_end == date(2026, 3, 31)
        assert yearly.deployment_frequency.value is not None
        assert yearly.deployment_frequency.value > 2.5
        assert yearly.deployment_frequency.trend == Trend.UP


def test_build_history_response_pagination_and_levels() -> None:
    with _session() as db:
        db.add(
            Repository(
                id=1,
                gitlab_id=1,
                name="a",
                path="g/a",
                default_branch="main",
                active=True,
            )
        )
        db.flush()
        periods = [
            (date(2026, 4, 7), date(2026, 4, 13)),
            (date(2026, 3, 31), date(2026, 4, 6)),
        ]
        for ps, pe in periods:
            db.add(
                MetricSnapshot(
                    repository_id=1,
                    period_type="WEEK",
                    period_start=ps,
                    period_end=pe,
                    deployment_freq=Decimal("1.5"),
                    lead_time_minutes=90,
                    release_wait_median_minutes=None,
                    change_failure_rate=Decimal("0.05"),
                    mttr_minutes=None,
                    mttr_alpha_minutes=80,
                    lead_post_production_median_minutes=None,
                    created_at=_utc_ts(ps.year, ps.month, ps.day),
                )
            )
        db.commit()

        hist = mps.build_history_response(
            db,
            period_type=PeriodType.WEEK,
            from_date=date(2026, 3, 1),
            to_date=date(2026, 5, 1),
            repository_id=None,
            page=0,
            size=1,
        )
        assert len(hist.data) == 1
        assert hist.pagination.total_elements == 2
        assert hist.pagination.has_next is True
        assert hist.data[0].performance_level.overall is not None

        hist2 = mps.build_history_response(
            db,
            period_type=PeriodType.WEEK,
            from_date=date(2026, 3, 1),
            to_date=date(2026, 5, 1),
            repository_id=None,
            page=0,
            size=500,
        )
        assert hist2.pagination.size == 100

        empty = mps.build_history_response(
            db,
            period_type=PeriodType.WEEK,
            from_date=date(2020, 1, 1),
            to_date=date(2020, 2, 1),
            repository_id=None,
            page=0,
            size=10,
        )
        assert empty.pagination.total_pages == 0
        assert empty.data == []


def test_build_history_response_clips_future_period_end_to_requested_to_date() -> None:
    with _session() as db:
        db.add(
            Repository(
                id=1,
                gitlab_id=1,
                name="a",
                path="g/a",
                default_branch="main",
                active=True,
            )
        )
        db.flush()
        db.add(
            MetricSnapshot(
                repository_id=1,
                period_type="QUARTER",
                period_start=date(2026, 4, 1),
                period_end=date(2026, 6, 30),
                deployment_freq=Decimal("1.0"),
                lead_time_minutes=60,
                release_wait_median_minutes=30,
                change_failure_rate=Decimal("0.1"),
                mttr_minutes=None,
                mttr_alpha_minutes=120,
                lead_post_production_median_minutes=None,
                created_at=_utc_ts(2026, 4, 22),
            )
        )
        db.commit()

        hist = mps.build_history_response(
            db,
            period_type=PeriodType.QUARTER,
            from_date=date(2025, 4, 22),
            to_date=date(2026, 4, 22),
            repository_id=None,
            page=0,
            size=10,
        )
        assert len(hist.data) == 1
        assert hist.data[0].period_start == date(2026, 4, 1)
        assert hist.data[0].period_end == date(2026, 4, 22)


def test_build_current_metrics_response_clips_future_window_end_to_today() -> None:
    with _session() as db:
        db.add(
            Repository(
                id=1,
                gitlab_id=1,
                name="a",
                path="g/a",
                default_branch="main",
                active=True,
            )
        )
        db.flush()
        today = datetime.now(timezone.utc).date()
        quarter_start = date(today.year, ((today.month - 1) // 3) * 3 + 1, 1)
        if quarter_start.month == 10:
            quarter_end = date(quarter_start.year + 1, 1, 1) - timedelta(days=1)
        else:
            quarter_end = date(quarter_start.year, quarter_start.month + 3, 1) - timedelta(days=1)
        db.add(
            MetricSnapshot(
                repository_id=1,
                period_type="QUARTER",
                period_start=quarter_start,
                period_end=quarter_end,
                deployment_freq=Decimal("1.0"),
                lead_time_minutes=60,
                release_wait_median_minutes=30,
                change_failure_rate=Decimal("0.1"),
                mttr_minutes=None,
                mttr_alpha_minutes=120,
                lead_post_production_median_minutes=None,
                created_at=_utc_ts(today.year, today.month, max(1, min(today.day, 28))),
            )
        )
        db.commit()

        cur = mps.build_current_metrics_response(db, repository_id=1, period_type="QUARTER")
        assert cur.period_end <= today
