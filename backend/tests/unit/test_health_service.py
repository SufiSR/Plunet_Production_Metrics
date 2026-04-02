from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.models.sync_log import SyncLog
from app.services.health_service import build_health_response


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)
    return maker()


def test_build_health_response_happy_path() -> None:
    at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with _session() as db:
        db.add(
            SyncLog(
                id=1,
                source="gitlab",
                started_at=at,
                finished_at=at,
                status="success",
                records_processed=1,
                error_message=None,
                details_json=None,
            )
        )
        db.add(
            SyncLog(
                id=2,
                source="jira",
                started_at=at,
                finished_at=at,
                status="success",
                records_processed=1,
                error_message=None,
                details_json=None,
            )
        )
        db.commit()
        resp = build_health_response(db)
    assert resp.status == "UP"
    assert resp.components["database"].status == "UP"
    assert resp.components["gitlab"].status == "UP"
    assert resp.components["jira"].status == "UP"


def test_build_health_response_database_failure() -> None:
    db = MagicMock()
    db.execute.side_effect = RuntimeError("db down")
    db.scalar.return_value = None
    resp = build_health_response(db)
    assert resp.components["database"].status == "DOWN"
    assert resp.status == "DOWN"
    assert resp.components["gitlab"].status == "DOWN"
