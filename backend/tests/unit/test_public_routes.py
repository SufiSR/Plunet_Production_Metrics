from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

import app.database as database
from app.api.deps import get_db
from app.models import Base
from app.models.release import Release
from app.models.repository import Repository


@pytest.fixture
def public_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "public_routes.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path.resolve().as_posix()}")
    monkeypatch.setenv("DORA_SESSION_SECRET", "unit-test-session-secret-strings")
    monkeypatch.setenv("DORA_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("DORA_ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("CONFIG_ENCRYPTION_KEY", "devops-438-key")
    for key in (
        "GITLAB_BASE_URL",
        "GITLAB_TOKEN",
        "GITLAB_API_TOKEN",
        "JIRA_BASE_URL",
        "JIRA_API_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)

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


def test_health_includes_components(public_client: TestClient) -> None:
    response = public_client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "UP"
    assert set(body["components"].keys()) == {"database", "gitlab", "jira"}


def test_repositories_empty(public_client: TestClient) -> None:
    response = public_client.get("/api/repositories")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["repositories"] == []


def test_metrics_current_empty_window(public_client: TestClient) -> None:
    response = public_client.get("/api/metrics/current")
    assert response.status_code == 200
    body = response.json()
    assert body["repository_count"] == 0


def test_metrics_repository_not_found(public_client: TestClient) -> None:
    response = public_client.get("/api/metrics/repository/99999")
    assert response.status_code == 404


def test_metrics_history_defaults(public_client: TestClient) -> None:
    response = public_client.get("/api/metrics/history")
    assert response.status_code == 200
    body = response.json()
    assert body["period_type"] == "WEEK"
    assert "from" in body
    assert "to" in body
    assert body["pagination"]["page"] == 0


def test_sync_status_shape(public_client: TestClient) -> None:
    response = public_client.get("/api/sync/status")
    assert response.status_code == 200
    body = response.json()
    assert "sync_schedule_cron" in body
    assert "last_sync" in body


def test_release_timeline_contains_release_events(public_client: TestClient) -> None:
    with Session(database.get_engine()) as db:
        db.add(
            Repository(
                id=1,
                gitlab_id=1,
                name="plunet",
                path="dev/plunet",
                default_branch="main",
                active=True,
            )
        )
        db.add(
            Release(
                id=1,
                repository_id=1,
                    tag_name="v10.2.3",
                customer_release=True,
                    version_major=10,
                version_minor=2,
                version_patch=3,
                commit_sha="abc123abc123abc123abc123abc123abc123abc1",
                committed_at=datetime(2026, 4, 10, 8, 30, tzinfo=timezone.utc),
            )
        )
        db.commit()

    response = public_client.get("/api/metrics/releases/timeline")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["tag_name"] == "v10.2.3"
    assert body["items"][0]["customer_release"] is True
    assert body["items"][0]["repository_path"] == "dev/plunet"
