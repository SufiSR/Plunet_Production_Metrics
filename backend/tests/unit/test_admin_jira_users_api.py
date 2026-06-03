from __future__ import annotations

from collections.abc import Generator
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

import app.database as database
import app.models  # noqa: F401
from app.api.deps import get_db
from app.jira_analytics.models import AllocationRoleRule, JiraUser
from app.models import Base


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "jira_users_api.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path.resolve().as_posix()}")
    monkeypatch.setenv("DORA_SESSION_SECRET", "unit-test-session-secret-strings")
    monkeypatch.setenv("DORA_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("DORA_ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("CONFIG_ENCRYPTION_KEY", "devops-429-jira-users")
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


def _seed_user(db: Session) -> JiraUser:
    user = JiraUser(account_id="acc-1", display_name="Dev", email_address="dev@test.com")
    db.add(user)
    db.add(
        AllocationRoleRule(
            role_name="Developer",
            is_direct_production_role=True,
            is_indirect_role=False,
            overhead_percentage=Decimal(0),
            allocation_scope="direct_issue",
            allocation_base="direct_production_hours",
        )
    )
    db.add(
        AllocationRoleRule(
            role_name="Solutions Engineer",
            is_direct_production_role=True,
            is_indirect_role=False,
            overhead_percentage=Decimal(0),
            allocation_scope="direct_issue",
            allocation_base="direct_production_hours",
        )
    )
    db.commit()
    return user


def test_jira_users_requires_admin(client: TestClient) -> None:
    assert client.get("/api/admin/jira-users").status_code == 401


def test_jira_users_crud_flow(client: TestClient) -> None:
    db = sessionmaker(bind=database.get_engine())()
    user = _seed_user(db)
    user_id = user.id
    db.close()

    client.post("/api/auth/login", json={"username": "admin", "password": "secret"})
    listed = client.get("/api/admin/jira-users")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total_elements"] >= 1

    patched = client.patch(
        f"/api/admin/jira-users/{user_id}",
        json={"reporting_excluded": True},
    )
    assert patched.status_code == 200
    assert patched.json()["reporting_excluded"] is True

    put = client.put(
        f"/api/admin/jira-users/{user_id}/role-assignment",
        json={"role_name": "Developer", "team_name": "Alpha"},
    )
    assert put.status_code == 200
    assert put.json()["role_assignment"]["role_name"] == "Developer"

    rules = client.get("/api/admin/jira-users/allocation-role-rules")
    assert rules.status_code == 200
    assert any(r["role_name"] == "Developer" for r in rules.json()["items"])
    assert any(
        r["role_name"] == "Solutions Engineer" and r["is_indirect_role"] is False
        for r in rules.json()["items"]
    )
