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
from app.models.merge_request import MergeRequest
from app.models.production_bug import ProductionBug
from app.models.release import Release
from app.models.repository import Repository


@pytest.fixture
def data_health_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "data_health.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path.resolve().as_posix()}")
    monkeypatch.setenv("DORA_SESSION_SECRET", "unit-test-session-secret-strings")
    monkeypatch.setenv("DORA_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("DORA_ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("CONFIG_ENCRYPTION_KEY", "devops-438-key")
    monkeypatch.setenv("GITLAB_BASE_URL", "https://gitlab.example.com")
    monkeypatch.setenv("GITLAB_API_TOKEN", "token")
    monkeypatch.setenv("JIRA_BASE_URL", "https://plunet.atlassian.net")
    monkeypatch.setenv("JIRA_USER_EMAIL", "devops@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "jira-token")

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


def _utc(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


def test_data_health_requires_admin_session(data_health_client: TestClient) -> None:
    response = data_health_client.get("/api/admin/data-health")
    assert response.status_code == 401
    assert response.json()["error"] == "UNAUTHORIZED"


def test_data_health_response_contains_required_sections(data_health_client: TestClient) -> None:
    with Session(database.get_engine()) as db:
        db.add(
            Repository(
                id=1,
                gitlab_id=111,
                name="repo",
                path="group/repo",
                default_branch="main",
                active=True,
            )
        )
        db.add(
            Release(
                id=1,
                repository_id=1,
                tag_name="v11.0.0",
                customer_release=True,
                version_major=11,
                version_minor=0,
                version_patch=0,
                commit_sha="a" * 40,
                committed_at=_utc(2026, 4, 1),
            )
        )
        db.add(
            MergeRequest(
                id=1,
                repository_id=1,
                gitlab_mr_id=100,
                title="Missing customer tag",
                target_branch="main",
                created_at=_utc(2026, 4, 2),
                merged_at=_utc(2026, 4, 3),
                first_customer_tag=None,
                jira_key="DEVOPS-1",
            )
        )
        db.add(
            MergeRequest(
                id=2,
                repository_id=1,
                gitlab_mr_id=101,
                title="Has customer tag but no jira key",
                target_branch="main",
                created_at=_utc(2026, 4, 4),
                merged_at=_utc(2026, 4, 5),
                first_customer_tag="v11.0.0",
                jira_key=None,
                lead_time_match_status="matched",
            )
        )
        db.add(
            ProductionBug(
                id=1,
                jira_key="DEVOPS-10",
                summary="Healthy bug",
                healthy=True,
                healthmemo="post-production",
                jira_created_at_valid=True,
                affects_versions=["11.0.0"],
                fix_versions=["11.0.1"],
            )
        )
        db.add(
            ProductionBug(
                id=2,
                jira_key="DEVOPS-11",
                summary="Unhealthy bug",
                healthy=False,
                healthmemo="unhealthy - affected_version missing",
                jira_created_at_valid=True,
                affects_versions=["99.9.9"],
                fix_versions=[],
            )
        )
        db.add(
            ProductionBug(
                id=3,
                jira_key="DEVOPS-12",
                summary="Ignored bug",
                healthy=False,
                healthmemo="ignored",
                jira_created_at_valid=True,
                affects_versions=["11.0.0"],
                fix_versions=[],
            )
        )
        db.commit()

    login = data_health_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "secret"},
    )
    assert login.status_code == 200

    response = data_health_client.get(
        "/api/admin/data-health",
        params={"unmatched_page": 0, "unmatched_size": 10, "mismatch_page": 0, "mismatch_size": 10},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["summary"]["total_bugs"] == 3
    assert body["summary"]["healthy_bugs"] == 2
    assert body["summary"]["healthy_bugs_pct"] == 66.67
    assert body["summary"]["unmatched_mr_count"] == 2
    assert body["summary"]["version_mismatch_count"] == 2

    ignored_breakdown = next(row for row in body["jira_health_breakdown"] if row["healthmemo"] == "ignored")
    assert ignored_breakdown["healthy"] is True
    assert body["unmatched_merge_requests_pagination"]["total_elements"] == 2
    assert len(body["unmatched_merge_requests"]) == 2
    assert body["unmatched_merge_requests"][0]["gitlab_merge_request_url"]
    assert any(row["jira_browse_url"] for row in body["unmatched_merge_requests"])

    assert body["version_mismatches_pagination"]["total_elements"] == 2
    assert len(body["version_mismatches"]) == 2
    assert body["version_mismatches"][0]["jira_browse_url"]
