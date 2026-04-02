from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config_schema import ConfigurationSchema
from app.models.base import Base
from app.models.sync_log import SyncLog
from app.services.sync_status_service import (
    _map_run_status,
    _parse_iso_dt,
    build_sync_status_response,
)


def test_map_run_status() -> None:
    assert _map_run_status("success") == "SUCCESS"
    assert _map_run_status("partial_failure") == "PARTIAL_FAILURE"
    assert _map_run_status("failed") == "FAILED"
    assert _map_run_status("crashed") == "FAILED"
    assert _map_run_status("running") == "FAILED"
    assert _map_run_status("unknown") == "FAILED"


def test_parse_iso_dt() -> None:
    assert _parse_iso_dt(None) is None
    naive = datetime(2026, 1, 1, 12, 0, 0)
    out = _parse_iso_dt(naive)
    assert out is not None and out.tzinfo == timezone.utc
    aware = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert _parse_iso_dt(aware) is aware
    assert _parse_iso_dt("2026-01-01T12:00:00Z") is not None
    assert _parse_iso_dt("not-a-date") is None
    assert _parse_iso_dt(123) is None


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)
    return maker()


def test_build_sync_status_no_log(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.sync_status_service.get_scheduler",
        lambda: None,
    )
    cfg = ConfigurationSchema()
    with _session() as db:
        resp = build_sync_status_response(db, config=cfg)
    assert resp.last_sync is None
    assert "0 2 * * *" in resp.sync_schedule_cron


def test_build_sync_status_with_scheduler_next_run(monkeypatch: pytest.MonkeyPatch) -> None:
    job = MagicMock()
    job.next_run_time = datetime(2026, 6, 1, 2, 0, 0)
    sched = MagicMock()
    sched.running = True
    sched.get_job.return_value = job
    monkeypatch.setattr(
        "app.services.sync_status_service.get_scheduler",
        lambda: sched,
    )
    cfg = ConfigurationSchema()
    with _session() as db:
        resp = build_sync_status_response(db, config=cfg)
    assert resp.next_scheduled_sync is not None
    assert resp.next_scheduled_sync.tzinfo == timezone.utc


def test_build_sync_status_collectors_and_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.sync_status_service.get_scheduler",
        lambda: None,
    )
    started = datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)
    started_newer = datetime(2026, 1, 1, 1, 10, tzinfo=timezone.utc)
    finished = datetime(2026, 1, 1, 1, 15, tzinfo=timezone.utc)
    cfg = ConfigurationSchema()
    with _session() as db:
        db.add(
            SyncLog(
                id=1,
                source="nightly",
                started_at=started,
                    finished_at=datetime(2026, 1, 1, 1, 5, tzinfo=timezone.utc),
                    status="success",
                    records_processed=None,
                    error_message=None,
                    details_json={},
                )
            )
        db.add(
            SyncLog(
                id=2,
                source="nightly",
                started_at=started_newer,
                finished_at=finished,
                status="success",
                records_processed=None,
                error_message=None,
                details_json={
                    "collectors": {
                        "gitlab": {"status": "success", "records_processed": {"x": 1}},
                        "jira": {"status": "oops"},
                    },
                    "snapshots_generated": 3,
                    "snapshot_generated_at": "2026-01-01T01:04:00+00:00",
                },
            )
        )
        db.commit()
        resp = build_sync_status_response(db, config=cfg)
    assert resp.last_sync is not None
    assert resp.last_sync.status == "SUCCESS"
    assert resp.last_sync.duration_seconds == 5 * 60
    assert resp.last_sync.collectors["gitlab"].status == "success"
    assert resp.last_sync.collectors["jira"].status == "oops"
    assert resp.last_sync.snapshots_generated == 3
    assert resp.last_sync.snapshot_generated_at is not None


def test_build_sync_status_non_dict_collectors_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.sync_status_service.get_scheduler",
        lambda: None,
    )
    started = datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)
    cfg = ConfigurationSchema()
    with _session() as db:
        db.add(
            SyncLog(
                id=1,
                source="nightly",
                started_at=started,
                finished_at=None,
                status="failed",
                records_processed=None,
                error_message=None,
                details_json={"collectors": "broken", "duration_seconds": 42},
            )
        )
        db.commit()
        resp = build_sync_status_response(db, config=cfg)
    assert resp.last_sync is not None
    assert resp.last_sync.collectors["gitlab"].status == "FAILED"
    assert resp.last_sync.duration_seconds == 42


def test_build_sync_status_row_with_null_started_at(monkeypatch: pytest.MonkeyPatch) -> None:
    """ORM rows normally always have started_at; this covers the defensive branch."""
    monkeypatch.setattr(
        "app.services.sync_status_service.get_scheduler",
        lambda: None,
    )
    row = MagicMock()
    row.started_at = None
    row.finished_at = None
    row.status = "success"
    row.details_json = {}
    scalars_chain = MagicMock()
    scalars_chain.first.return_value = row
    db = MagicMock()
    db.scalars.return_value = scalars_chain
    db.scalar.return_value = None
    cfg = ConfigurationSchema()
    resp = build_sync_status_response(db, config=cfg)
    assert resp.last_sync is not None
    assert resp.last_sync.started_at.tzinfo is not None
