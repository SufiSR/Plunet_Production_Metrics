from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.config_schema import ConfigurationSchema
from app.models.base import Base
from app.models.merge_request import MergeRequest
from app.models.production_bug import ProductionBug
from app.models.release import Release
from app.models.repository import Repository
from app.models.sync_log import SyncLog
from app.services import gitlab_release_collector as gl_mod
from app.services import jira_bug_collector as jira_mod
from app.services.gitlab_release_collector import collect_gitlab_tags_and_releases
from app.services.jira_bug_collector import hydrate_merge_request_jira_ready_for_qa


@pytest.fixture(autouse=True)
def _sqlite_bigint_pk_autogen() -> None:
    """Assign SQLite-friendly monotonic ids for BIGINT PK tables in this module."""

    from app.models.production_bug import ProductionBug
    from app.models.release import Release
    from app.models.sync_log import SyncLog

    def _assign_id(mapper, connection, target):  # type: ignore[no-untyped-def]
        if getattr(target, "id", None) is not None:
            return
        tablename = target.__table__.name
        raw = connection.execute(
            text(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {tablename}")
        ).scalar()
        target.id = int(raw)

    models = (SyncLog, Release, ProductionBug)
    for m in models:
        event.listen(m, "before_insert", _assign_id)
    yield
    for m in models:
        event.remove(m, "before_insert", _assign_id)


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)
    return maker()


def test_collect_gitlab_inserts_release_and_success_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeGitLab:
        def __init__(self, base_url: str, token: str, timeout_seconds: float = 30.0) -> None:
            self._token = token

        def __enter__(self) -> FakeGitLab:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def close(self) -> None:
            pass

        def get_project(self, project_path: str) -> dict[str, object]:
            return {
                "id": 8801,
                "name": "repo",
                "path_with_namespace": project_path,
                "default_branch": "main",
            }

        def list_tags(self, project_path: str, per_page: int = 100) -> list[dict[str, object]]:
            _ = (project_path, per_page)
            return [
                {
                    "name": "v10.0.0",
                    "commit": {
                        "id": "f" * 40,
                        "committed_date": "2026-04-10T12:00:00Z",
                    },
                }
            ]

        def list_merged_merge_requests(
            self,
            project_path: str,
            *,
            target_branch: str,
            lookback_days: int,
            per_page: int = 100,
        ) -> list[dict[str, object]]:
            _ = (project_path, target_branch, lookback_days, per_page)
            return []

    monkeypatch.setattr(gl_mod, "GitLabTagsClient", FakeGitLab)

    cfg = ConfigurationSchema.model_validate(
        {
            "gitlab": {
                "base_url": "https://gitlab.test",
                "project_paths": ["operations/sample"],
                "target_branches": ["main"],
            },
            "backend": {"lookback_days": 30},
        }
    )
    with _session() as db:
        processed = collect_gitlab_tags_and_releases(
            db,
            config=cfg,
            gitlab_token="glpat-test",
            mr_mapping_cooldown_seconds=0.0,
        )
        log = db.scalars(
            select(SyncLog).where(SyncLog.source == "gitlab").order_by(SyncLog.id.desc())
        ).first()
        tag_names = db.scalars(
            select(Release.tag_name).where(Release.repository_id == 8801)
        ).all()

    assert processed >= 1
    assert log is not None
    assert log.status == "success"
    assert log.records_processed == processed
    assert "v10.0.0" in tag_names


def test_collect_gitlab_failure_writes_failed_sync_log(monkeypatch: pytest.MonkeyPatch) -> None:
    class BoomGitLab:
        def __init__(self, *_a: object, **_k: object) -> None:
            pass

        def __enter__(self) -> BoomGitLab:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def close(self) -> None:
            pass

        def get_project(self, _path: str) -> dict[str, object]:
            raise RuntimeError("gitlab unavailable")

    monkeypatch.setattr(gl_mod, "GitLabTagsClient", BoomGitLab)
    cfg = ConfigurationSchema.model_validate(
        {
            "gitlab": {"project_paths": ["x/y"], "target_branches": ["main"]},
        }
    )
    with _session() as db:
        with pytest.raises(RuntimeError, match="gitlab unavailable"):
            collect_gitlab_tags_and_releases(db, config=cfg, gitlab_token="t")
        failed = db.scalars(
            select(SyncLog).where(SyncLog.source == "gitlab", SyncLog.status == "failed")
        ).first()
    assert failed is not None
    assert failed.error_message is not None


def test_collect_jira_upserts_bug_and_marks_sync_success(monkeypatch: pytest.MonkeyPatch) -> None:
    issue = {
        "key": "DM-100",
        "changelog": {
            "histories": [
                {
                    "created": "2026-04-01T09:00:00.000+0000",
                    "items": [{"field": "status", "toString": "Ready for QA"}],
                }
            ],
            "total": 1,
        },
        "fields": {
            "summary": "Sample bug",
            "issuetype": {"name": "Bug"},
            "status": {"name": "Closed"},
            "priority": {"name": "Critical"},
            "created": "2026-04-01T08:00:00.000+0000",
            "updated": "2026-04-02T08:00:00.000+0000",
            "resolutiondate": "2026-04-03T08:00:00.000+0000",
            "versions": [{"name": "10.0.0"}],
            "fixVersions": [{"name": "10.0.1"}],
            "components": [],
            "customfield_10114": "https://help.example/browse/CS-1",
            "customfield_10123": [{"name": "Acme Corp"}],
        },
    }

    class FakeJira:
        def __init__(self, *_a: object, **_k: object) -> None:
            pass

        def __enter__(self) -> FakeJira:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def close(self) -> None:
            pass

        def search_bugs(self, **_kwargs: object) -> list[dict[str, object]]:
            return [issue]

        def list_issue_changelog(self, *_a: object, **_k: object) -> list[dict[str, object]]:
            raise AssertionError("changelog embedded in search response")

        def list_issue_worklogs(self, *_a: object, **_k: object) -> list[dict[str, object]]:
            return []

    monkeypatch.setattr(jira_mod, "JiraBugsClient", FakeJira)
    cfg = ConfigurationSchema.model_validate(
        {
            "jira": {"ready_for_qa_status_names": ["Ready for QA"]},
            "backend": {"lookback_days": 14},
        }
    )
    with _session() as db:
        processed = jira_mod.collect_jira_production_bugs(db, config=cfg, jira_token="jira-token")
        log = db.scalars(
            select(SyncLog).where(SyncLog.source == "jira").order_by(SyncLog.id.desc())
        ).first()
        bug = db.scalars(select(ProductionBug).where(ProductionBug.jira_key == "DM-100")).first()

    assert processed == 1
    assert log is not None and log.status == "success"
    assert bug is not None
    assert bug.healthy is True
    assert bug.ready_for_qa_at is not None


def test_hydrate_merge_request_skips_when_jira_token_missing() -> None:
    with _session() as db:
        n = hydrate_merge_request_jira_ready_for_qa(
            db,
            config=ConfigurationSchema(),
            jira_token="",
        )
    assert n == 0


def test_hydrate_merge_request_fetches_changelog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    changelog_calls: list[str] = []

    class FakeJira:
        def __init__(self, *_a: object, **_k: object) -> None:
            pass

        def __enter__(self) -> FakeJira:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def close(self) -> None:
            pass

        def list_issue_changelog(
            self,
            issue_key: str,
            *,
            max_results: int = 100,
        ) -> list[dict[str, object]]:
            _ = max_results
            changelog_calls.append(issue_key)
            return [
                {
                    "created": "2026-04-01T10:00:00.000+0000",
                    "items": [{"field": "status", "toString": "Ready for QA"}],
                }
            ]

    monkeypatch.setattr(jira_mod, "JiraBugsClient", FakeJira)
    cfg = ConfigurationSchema.model_validate(
        {"jira": {"ready_for_qa_status_names": ["Ready for QA"]}}
    )
    with _session() as db:
        db.add(
            Repository(
                id=1,
                gitlab_id=1,
                name="r",
                path="g/r",
                default_branch="main",
                active=True,
            )
        )
        db.flush()
        db.add(
            MergeRequest(
                id=50,
                repository_id=1,
                gitlab_mr_id=10,
                target_branch="main",
                created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
                merged_at=datetime(2026, 4, 2, tzinfo=timezone.utc),
                jira_key="FEAT-9",
            )
        )
        db.commit()
        touched = hydrate_merge_request_jira_ready_for_qa(db, config=cfg, jira_token="tok")
        mr = db.get(MergeRequest, 50)
    assert touched == 1
    assert changelog_calls == ["FEAT-9"]
    assert mr is not None
    assert mr.jira_ready_for_qa_at is not None


def test_gitlab_tags_client_get_json_wraps_4xx_as_runtime_error() -> None:
    from app.services.gitlab_release_collector import GitLabTagsClient

    client = GitLabTagsClient("https://gitlab.example", "tok")
    try:

        def fake_get(*_a: object, **_k: object) -> httpx.Response:
            req = httpx.Request("GET", "https://gitlab.example/api/v4/x")
            return httpx.Response(404, request=req)

        client.client.get = fake_get  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="GitLab API request failed: 404"):
            client._get_json("https://gitlab.example/api/v4/x")
    finally:
        client.close()


def test_is_retryable_http_exception_gitlab() -> None:
    req = httpx.Request("GET", "https://example.com")
    assert gl_mod._is_retryable_http_exception(httpx.ConnectError("boom", request=req))
    exc_500 = httpx.HTTPStatusError(
        "s",
        request=req,
        response=httpx.Response(500, request=req),
    )
    assert gl_mod._is_retryable_http_exception(exc_500)
    exc_429 = httpx.HTTPStatusError(
        "s",
        request=req,
        response=httpx.Response(429, request=req),
    )
    assert gl_mod._is_retryable_http_exception(exc_429)
    exc_404 = httpx.HTTPStatusError(
        "s",
        request=req,
        response=httpx.Response(404, request=req),
    )
    assert not gl_mod._is_retryable_http_exception(exc_404)
