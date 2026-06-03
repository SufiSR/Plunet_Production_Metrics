from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

import app.database as database
from app.api.deps import get_db
from app.models import Base


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "hrworks_api.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path.resolve().as_posix()}")
    monkeypatch.setenv("DORA_SESSION_SECRET", "unit-test-session-secret-strings")
    monkeypatch.setenv("DORA_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("DORA_ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("CONFIG_ENCRYPTION_KEY", "devops-429-hrworks")
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


def test_hrworks_sync_trigger_requires_admin(client: TestClient) -> None:
    response = client.post("/api/admin/hrworks/sync/trigger")

    assert response.status_code == 401


def test_hrworks_sync_trigger_dispatches_background_thread(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.admin_hrworks as admin_hrworks

    called: list[bool] = []

    def fake_run(*, incremental: bool) -> None:
        assert incremental is False
        called.append(True)

    class ImmediateThread:
        def __init__(self, *, target, name: str, daemon: bool) -> None:  # type: ignore[no-untyped-def]
            self.target = target
            self.name = name
            self.daemon = daemon

        def start(self) -> None:
            self.target()

    monkeypatch.setattr(admin_hrworks, "_run_manual_hrworks_sync_in_thread", fake_run)
    monkeypatch.setattr(admin_hrworks.threading, "Thread", ImmediateThread)
    client.post("/api/auth/login", json={"username": "admin", "password": "secret"})

    response = client.post("/api/admin/hrworks/sync/trigger")

    assert response.status_code == 202
    assert response.json() == {"detail": "HRworks sync triggered"}
    assert called == [True]


def test_latest_hrworks_sync_empty_state(client: TestClient) -> None:
    client.post("/api/auth/login", json={"username": "admin", "password": "secret"})

    response = client.get("/api/admin/hrworks/sync/latest")

    assert response.status_code == 200
    assert response.json() == {"status": None, "sync_log": None}
