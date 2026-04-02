from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config_schema import ConfigurationSchema
from app.models.base import Base
from app.services.snapshot_service import (
    _next_period_start,
    _period_end,
    _period_start,
    refresh_snapshots,
)


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)
    return maker()


def test_refresh_snapshots_no_active_repositories() -> None:
    with _session() as db:
        written = refresh_snapshots(
            db,
            config=ConfigurationSchema(),
            now=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
    assert written == 0


def test_period_helpers_reject_unknown_type() -> None:
    d = date(2026, 2, 15)
    with pytest.raises(ValueError, match="Unsupported period type"):
        _period_start("INVALID", d)
    with pytest.raises(ValueError, match="Unsupported period type"):
        _period_end("INVALID", d)
    with pytest.raises(ValueError, match="Unsupported period type"):
        _next_period_start("INVALID", d)
