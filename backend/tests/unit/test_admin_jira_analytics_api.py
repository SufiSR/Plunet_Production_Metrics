from __future__ import annotations

from collections.abc import Generator
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

import app.database as database
from app.api.deps import get_db
from app.models import Base


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "jira_analytics_api.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path.resolve().as_posix()}")
    monkeypatch.setenv("DORA_SESSION_SECRET", "unit-test-session-secret-strings")
    monkeypatch.setenv("DORA_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("DORA_ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("CONFIG_ENCRYPTION_KEY", "devops-429-jira-analytics")
    database._engine = None
    Base.metadata.create_all(database.get_engine())
    maker = sessionmaker(
        bind=database.get_engine(),
        class_=Session,
        autoflush=False,
        autocommit=False,
    )

    def _db() -> Generator[Session, None, None]:
        db = maker()
        try:
            yield db
        finally:
            db.close()

    from app.main import app

    app.dependency_overrides[get_db] = _db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_jira_analytics_sync_trigger_requires_admin(client: TestClient) -> None:
    response = client.post("/api/admin/jira-analytics/sync/trigger")

    assert response.status_code == 401


def test_jira_analytics_sync_trigger_dispatches_background_thread(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.admin_jira_analytics as admin_jira_analytics

    called: list[bool] = []

    def fake_run() -> None:
        called.append(True)

    class ImmediateThread:
        def __init__(self, *, target, name: str, daemon: bool) -> None:  # type: ignore[no-untyped-def]
            self.target = target
            self.name = name
            self.daemon = daemon

        def start(self) -> None:
            self.target()

    captured: list[int | None] = []

    def fake_run(*, updated_after_days: int | None) -> None:
        captured.append(updated_after_days)
        called.append(True)

    monkeypatch.setattr(admin_jira_analytics, "_run_manual_jira_analytics_sync_in_thread", fake_run)
    monkeypatch.setattr(admin_jira_analytics.threading, "Thread", ImmediateThread)
    client.post("/api/auth/login", json={"username": "admin", "password": "secret"})

    response = client.post("/api/admin/jira-analytics/sync/trigger?updated_after_days=7")

    assert response.status_code == 202
    body = response.json()
    assert body["detail"] == "Jira analytics sync triggered (updated >= -7d)"
    assert body["updated_after_days"] == 7
    assert called == [True]
    assert captured == [7]


def test_latest_jira_analytics_sync_empty_state(client: TestClient) -> None:
    client.post("/api/auth/login", json={"username": "admin", "password": "secret"})

    response = client.get("/api/admin/jira-analytics/sync/latest")

    assert response.status_code == 200
    assert response.json() == {"status": None, "sync_log": None}


def test_jira_analytics_allocation_rebuild_requires_admin(client: TestClient) -> None:
    response = client.post("/api/admin/jira-analytics/rebuild-allocation")

    assert response.status_code == 401


def test_jira_analytics_allocation_rebuild_dispatches_background_thread(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.admin_jira_analytics as admin_jira_analytics

    called: list[bool] = []

    class ImmediateThread:
        def __init__(self, *, target, name: str, daemon: bool) -> None:  # type: ignore[no-untyped-def]
            self.target = target
            self.name = name
            self.daemon = daemon

        def start(self) -> None:
            called.append(True)

    monkeypatch.setattr(admin_jira_analytics.threading, "Thread", ImmediateThread)
    client.post("/api/auth/login", json={"username": "admin", "password": "secret"})

    response = client.post("/api/admin/jira-analytics/rebuild-allocation")

    assert response.status_code == 202
    body = response.json()
    assert body["state"] == "running"
    assert body["message"] == "Allocation rebuild started for 0 months."
    assert called == [True]
    admin_jira_analytics._allocation_rebuild_status["state"] = "idle"


def test_jira_analytics_allocation_rebuild_period_runs_synchronously(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.admin_jira_analytics as admin_jira_analytics

    captured_months: list[list[date] | None] = []

    def fake_rebuild(db, *, settings_json=None, period_months=None):  # type: ignore[no-untyped-def]
        captured_months.append(period_months)
        return {
            "periods": ["2026-05-01"],
            "topic_rows": 2,
            "allocation_rows": 3,
        }

    monkeypatch.setattr(admin_jira_analytics, "rebuild_monthly_allocation", fake_rebuild)
    client.post("/api/auth/login", json={"username": "admin", "password": "secret"})

    response = client.post("/api/admin/jira-analytics/rebuild-allocation?period_month=2026-05-22")

    assert response.status_code == 200
    assert response.json() == {
        "state": "succeeded",
        "periods": ["2026-05-01"],
        "topic_rows": 2,
        "allocation_rows": 3,
    }
    assert captured_months == [[date(2026, 5, 1)]]
