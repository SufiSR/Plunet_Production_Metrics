from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.services import metric_service as ms
from app.services.metric_service import (
    calculate_deployment_frequency_per_week,
    classify_performance_level,
)


def test_classify_performance_level_requires_all_inputs() -> None:
    assert (
        classify_performance_level(
            deployment_freq_per_week=1.0,
            lead_time_minutes=100,
            change_failure_rate=0.1,
            mttr_minutes=None,
        )
        is None
    )


def test_calculate_deployment_frequency_zero_week_span() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with maker() as db:
        out = calculate_deployment_frequency_per_week(
            db,
            start_dt=t,
            end_dt=t,
            repository_id=1,
        )
    assert out == Decimal("0")


def test_internal_level_threshold_branches() -> None:
    assert ms._deployment_level(8.0) == "ELITE"
    assert ms._deployment_level(1.0) == "HIGH"
    assert ms._deployment_level(0.3) == "MEDIUM"
    assert ms._deployment_level(0.1) == "LOW"

    assert ms._lead_time_level(30) == "ELITE"
    assert ms._lead_time_level(3 * 24 * 60) == "HIGH"
    assert ms._lead_time_level(20 * 24 * 60) == "MEDIUM"
    assert ms._lead_time_level(40 * 24 * 60) == "LOW"

    assert ms._cfr_level(0.04) == "ELITE"
    assert ms._cfr_level(0.08) == "HIGH"
    assert ms._cfr_level(0.12) == "MEDIUM"
    assert ms._cfr_level(0.20) == "LOW"

    assert ms._mttr_level(30) == "ELITE"
    assert ms._mttr_level(2 * 60) == "HIGH"
    assert ms._mttr_level(5 * 24 * 60) == "MEDIUM"
    assert ms._mttr_level(10 * 24 * 60) == "LOW"


def test_median_minute_helpers_empty() -> None:
    assert ms._median_minutes_from_hours([]) is None
    assert ms._median_minutes_from_hours([None]) is None
    assert ms._median_minutes([]) is None
