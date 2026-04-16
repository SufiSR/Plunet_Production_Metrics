from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

import app.database as database
from app.api.deps import get_db
from app.models import Base
from app.models.bug_release import BugRelease
from app.models.merge_request import MergeRequest
from app.models.production_bug import ProductionBug
from app.models.release import Release
from app.models.repository import Repository
from app.services.release_drilldown_service import build_gitlab_compare_url, build_jira_browse_url


@pytest.fixture
def drilldown_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "drilldown.sqlite"
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


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def test_customer_drilldown_pagination_and_mr_list(drilldown_client: TestClient) -> None:
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
        # Three customer releases, newest first when sorted by committed_at desc
        rel_specs = [
            (1, "v11.0.2", 15, 2),
            (2, "v11.0.1", 10, 1),
            (3, "v11.0.0", 5, 0),
        ]
        for rid, tag, day, patch in rel_specs:
            db.add(
                Release(
                    id=rid,
                    repository_id=1,
                    tag_name=tag,
                    customer_release=True,
                    version_major=11,
                    version_minor=0,
                    version_patch=patch,
                    commit_sha=f"{'a' * 37}{rid:03d}"[:40],
                    committed_at=_utc(2026, 4, day, 12, 0),
                )
            )
        db.add(
            MergeRequest(
                id=1,
                repository_id=1,
                gitlab_mr_id=100,
                title="Fix thing",
                target_branch="main",
                created_at=_utc(2026, 4, 1),
                merged_at=_utc(2026, 4, 2),
                first_customer_tag="v11.0.2",
                first_customer_tag_date=_utc(2026, 4, 15, 12, 0),
                lead_time_hours=Decimal("48.5"),
                release_wait_time_hours=Decimal("12.0"),
                jira_key="DEVOPS-500",
            )
        )
        db.add(
            MergeRequest(
                id=2,
                repository_id=1,
                gitlab_mr_id=101,
                target_branch="11.x",
                created_at=_utc(2026, 4, 2),
                merged_at=_utc(2026, 4, 3),
                first_customer_tag="v11.0.2",
                first_customer_tag_date=_utc(2026, 4, 15, 12, 0),
                lead_time_hours=None,
                release_wait_time_hours=Decimal("6.0"),
                jira_key=None,
            )
        )
        db.commit()

    r1 = drilldown_client.get(
        "/api/metrics/releases/customer/drilldown",
        params={"page": 0, "size": 2},
    )
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["pagination"]["total_elements"] == 3
    assert body1["pagination"]["has_next"] is True
    assert len(body1["items"]) == 2
    assert body1["items"][0]["tag_name"] == "v11.0.2"
    assert body1["items"][0]["mr_count"] == 2
    assert body1["items"][0]["lane"] == "patch"

    r2 = drilldown_client.get(
        "/api/metrics/releases/customer/drilldown",
        params={"page": 1, "size": 2},
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["pagination"]["has_previous"] is True
    assert len(body2["items"]) == 1
    assert body2["items"][0]["tag_name"] == "v11.0.0"

    mr_resp = drilldown_client.get(
        "/api/metrics/releases/customer/merge-requests",
        params={"repository_id": 1, "tag_name": "v11.0.2", "page": 0, "size": 1},
    )
    assert mr_resp.status_code == 200
    mbody = mr_resp.json()
    assert mbody["pagination"]["total_elements"] == 2
    assert mbody["pagination"]["has_next"] is True
    assert len(mbody["items"]) == 1
    # merged_at desc: MR 101 merged Apr 3 before MR 100 Apr 2? desc means later first — 101 first
    assert mbody["items"][0]["gitlab_mr_id"] == 101
    assert mbody["previous_customer_tag"] == "v11.0.1"
    assert mbody["mr_with_jira_key_count"] == 1
    assert mbody.get("gitlab_compare_url")
    assert "v11.0.1" in mbody["gitlab_compare_url"]
    assert "v11.0.2" in mbody["gitlab_compare_url"]
    assert "dev/plunet/-/compare" in mbody["gitlab_compare_url"]
    assert "dev%2Fplunet" not in mbody["gitlab_compare_url"]

    mr_page1 = drilldown_client.get(
        "/api/metrics/releases/customer/merge-requests",
        params={"repository_id": 1, "tag_name": "v11.0.2", "page": 1, "size": 1},
    )
    assert mr_page1.json()["items"][0]["gitlab_mr_id"] == 100

    missing = drilldown_client.get(
        "/api/metrics/releases/customer/merge-requests",
        params={"repository_id": 1, "tag_name": "v99.0.0"},
    )
    assert missing.status_code == 404


def test_build_gitlab_compare_url_uses_literal_slashes_in_project_path() -> None:
    url = build_gitlab_compare_url(
        base_url="https://gitlab.plunet.com",
        project_path="dev/plunet",
        from_tag="v10.24.5",
        to_tag="v10.25.0",
    )
    assert url == (
        "https://gitlab.plunet.com/dev/plunet/-/compare/"
        "v10.24.5...v10.25.0"
    )


def test_build_gitlab_compare_url_encodes_spaces_inside_path_segments() -> None:
    url = build_gitlab_compare_url(
        base_url="https://gitlab.example.com",
        project_path="acme/R and D/app",
        from_tag="v1.0.0",
        to_tag="v1.0.1",
    )
    assert "acme/R%20and%20D/app/-/compare" in url


def test_drilldown_repository_filter_not_found(drilldown_client: TestClient) -> None:
    r = drilldown_client.get(
        "/api/metrics/releases/customer/drilldown",
        params={"repository_id": 999},
    )
    assert r.status_code == 404


def test_failed_drilldown_repository_filter_not_found(drilldown_client: TestClient) -> None:
    r = drilldown_client.get(
        "/api/metrics/releases/customer/failed-drilldown",
        params={"repository_id": 999},
    )
    assert r.status_code == 404


def test_build_jira_browse_url() -> None:
    url = build_jira_browse_url(
        base_url="https://plunet.atlassian.net",
        jira_key="DEVOPS-500",
    )
    assert url == "https://plunet.atlassian.net/browse/DEVOPS-500"


def test_failed_customer_release_drilldown_and_issues(drilldown_client: TestClient) -> None:
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
        for rid, tag, day, patch in [
            (1, "v11.0.2", 15, 2),
            (2, "v11.0.1", 10, 1),
            (3, "v11.0.0", 5, 0),
        ]:
            db.add(
                Release(
                    id=rid,
                    repository_id=1,
                    tag_name=tag,
                    customer_release=True,
                    version_major=11,
                    version_minor=0,
                    version_patch=patch,
                    commit_sha=f"{'b' * 37}{rid:03d}"[:40],
                    committed_at=_utc(2026, 4, day, 12, 0),
                )
            )
        db.add(
            ProductionBug(
                id=1,
                jira_key="DEVOPS-701",
                summary="Prod bug A",
                status="Open",
                priority="Critical",
                healthy=True,
                healthmemo="post-production",
                jira_created_at_valid=True,
            )
        )
        db.add(
            ProductionBug(
                id=2,
                jira_key="DEVOPS-702",
                summary="Prod bug B",
                status="Resolved",
                priority="Major",
                healthy=True,
                healthmemo="post-production",
                jira_created_at_valid=True,
            )
        )
        db.add(
            ProductionBug(
                id=3,
                jira_key="DEVOPS-703",
                summary="Unhealthy",
                healthy=False,
                healthmemo="unhealthy - affected_version missing",
                jira_created_at_valid=True,
            )
        )
        db.add(
            ProductionBug(
                id=4,
                jira_key="DEVOPS-704",
                summary="QA only",
                healthy=True,
                healthmemo="pre-production - parent is techsupport",
                jira_created_at_valid=True,
            )
        )
        db.add(BugRelease(bug_id=1, release_id=1))
        db.add(BugRelease(bug_id=2, release_id=1))
        db.add(BugRelease(bug_id=3, release_id=1))
        db.add(BugRelease(bug_id=4, release_id=1))
        db.add(BugRelease(bug_id=1, release_id=2))
        db.commit()

    fd = drilldown_client.get(
        "/api/metrics/releases/customer/failed-drilldown",
        params={"page": 0, "size": 10},
    )
    assert fd.status_code == 200
    body = fd.json()
    assert body["pagination"]["total_elements"] == 2
    assert len(body["items"]) == 2
    assert body["items"][0]["tag_name"] == "v11.0.2"
    assert body["items"][0]["issue_count"] == 2
    assert body["items"][1]["tag_name"] == "v11.0.1"
    assert body["items"][1]["issue_count"] == 1

    issues = drilldown_client.get(
        "/api/metrics/releases/customer/failed/issues",
        params={"repository_id": 1, "tag_name": "v11.0.2", "page": 0, "size": 1},
    )
    assert issues.status_code == 200
    ibody = issues.json()
    assert ibody["pagination"]["total_elements"] == 2
    assert ibody["pagination"]["has_next"] is True
    assert len(ibody["items"]) == 1
    assert ibody["items"][0]["jira_key"] == "DEVOPS-701"
    assert "atlassian.net/browse/DEVOPS-701" in (ibody["items"][0]["jira_browse_url"] or "")

    issues_p1 = drilldown_client.get(
        "/api/metrics/releases/customer/failed/issues",
        params={"repository_id": 1, "tag_name": "v11.0.2", "page": 1, "size": 1},
    )
    assert issues_p1.json()["items"][0]["jira_key"] == "DEVOPS-702"

    missing = drilldown_client.get(
        "/api/metrics/releases/customer/failed/issues",
        params={"repository_id": 1, "tag_name": "v99.0.0"},
    )
    assert missing.status_code == 404
