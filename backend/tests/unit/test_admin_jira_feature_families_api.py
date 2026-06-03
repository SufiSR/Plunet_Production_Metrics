from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

import app.database as database
import app.models  # noqa: F401
from app.api.deps import get_db
from app.jira_analytics.models import JiraFeatureRoot, JiraIssue, JiraProject
from app.models import Base


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "jira_feature_families_api.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path.resolve().as_posix()}")
    monkeypatch.setenv("DORA_SESSION_SECRET", "unit-test-session-secret-strings")
    monkeypatch.setenv("DORA_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("DORA_ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("CONFIG_ENCRYPTION_KEY", "devops-429-feature-families")
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


def _seed_feature(db: Session, *, key: str, summary: str) -> JiraFeatureRoot:
    project = JiraProject(jira_project_id=f"project-{key}", key="PMGT", name="PMGT")
    db.add(project)
    db.flush()
    issue = JiraIssue(
        jira_issue_id=f"issue-{key}",
        key=key,
        project_id=project.id,
        issue_type_name="Idea",
        summary=summary,
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(issue)
    db.flush()
    root = JiraFeatureRoot(
        root_issue_id=issue.id,
        root_key=key,
        root_project_key="PMGT",
        root_issue_type_name="Idea",
        name=summary,
        detection_rule="unit-test",
        active=True,
    )
    db.add(root)
    db.commit()
    return root


def test_feature_families_require_admin(client: TestClient) -> None:
    assert client.get("/api/admin/jira-feature-families").status_code == 401


def test_feature_family_crud_members_and_suggestions(client: TestClient) -> None:
    db = sessionmaker(bind=database.get_engine())()
    feature = _seed_feature(db, key="PMGT-1", summary="Invoice Import for Customer Portal")
    feature_id = feature.id
    db.close()

    client.post("/api/auth/login", json={"username": "admin", "password": "secret"})
    created = client.post(
        "/api/admin/jira-feature-families",
        json={"name": "Invoice Import", "suggestion_keywords": ["invoice", "import"]},
    )
    assert created.status_code == 201
    family_id = created.json()["family"]["id"]

    suggestions = client.get("/api/admin/jira-feature-families/suggestions")
    assert suggestions.status_code == 200
    suggestion_items = suggestions.json()["items"]
    assert suggestion_items
    suggestion_id = suggestion_items[0]["suggestion_id"]
    assert suggestion_items[0]["feature_root_id"] == feature_id

    accepted = client.post(
        f"/api/admin/jira-feature-families/suggestions/{suggestion_id}/accept",
        json={},
    )
    assert accepted.status_code == 200
    assert accepted.json()["family"]["member_count"] == 1

    listed_features = client.get("/api/admin/jira-feature-families/features")
    assert listed_features.status_code == 200
    assert listed_features.json()["items"][0]["assigned_family_id"] == family_id

    updated = client.put(
        f"/api/admin/jira-feature-families/{family_id}/members",
        json={"feature_root_ids": []},
    )
    assert updated.status_code == 200
    assert updated.json()["family"]["member_count"] == 0

    rejected = client.post(
        f"/api/admin/jira-feature-families/suggestions/{suggestion_id}/reject",
        json={"reason": "not the same family"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["items"] == []

