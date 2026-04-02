from __future__ import annotations

from datetime import datetime, timezone

import httpx
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.models.issue_worklog import IssueWorklog
from app.models.production_bug import ProductionBug
from app.services.jira_bug_collector import (
    HealthResult,
    JiraBugsClient,
    _build_bug_jql,
    _extract_named_values,
    _has_next_minor_marker,
    _is_retryable_http_exception,
    _lookback_from,
    _max_semver,
    _parse_dt,
    _parse_semver,
    _sync_issue_worklogs,
    _to_string_list,
    _upsert_production_bug,
    evaluate_issue_health,
    first_ready_for_qa_at,
    issue_changelog_histories_from_search_issue,
    parse_worklog_entry,
)


def test_health_healthy_post_production() -> None:
    result = evaluate_issue_health(
        issue_type="Bug",
        parent_type=None,
        parent_summary=None,
        affects_versions=["10.1.0"],
        fix_versions=["10.1.1"],
        indicator_cf10114="https://plunethelp.atlassian.net/browse/CS-123",
        customer_names=[],
        parent_affects_versions=[],
        parent_fix_versions=[],
        parent_indicator_cf10114=None,
        parent_customer_names=[],
    )
    assert result.healthy is True
    assert result.healthmemo == "post-production"


def test_health_pre_production_parent_override() -> None:
    result = evaluate_issue_health(
        issue_type="Bug Subtask",
        parent_type="Improvement",
        parent_summary="Work package",
        affects_versions=[],
        fix_versions=[],
        indicator_cf10114=None,
        customer_names=[],
        parent_affects_versions=[],
        parent_fix_versions=[],
        parent_indicator_cf10114=None,
        parent_customer_names=[],
    )
    assert result.healthy is True
    assert "pre-production - parent is Improvement" == result.healthmemo


def test_health_parent_second_pass_rescue() -> None:
    result = evaluate_issue_health(
        issue_type="Bug Subtask",
        parent_type="Bug",
        parent_summary="Incident parent",
        affects_versions=[],
        fix_versions=[],
        indicator_cf10114=None,
        customer_names=[],
        parent_affects_versions=["10.2.0"],
        parent_fix_versions=[],
        parent_indicator_cf10114="https://plunethelp.atlassian.net/browse/CS-999",
        parent_customer_names=[],
    )
    assert result.healthy is True
    assert result.healthmemo == "post-production due to parent"


def test_health_next_minor_global_override() -> None:
    result = evaluate_issue_health(
        issue_type="Bug",
        parent_type=None,
        parent_summary=None,
        affects_versions=["next minor - please branch from master"],
        fix_versions=[],
        indicator_cf10114=None,
        customer_names=[],
        parent_affects_versions=[],
        parent_fix_versions=[],
        parent_indicator_cf10114=None,
        parent_customer_names=[],
    )
    assert result.healthy is True
    assert result.healthmemo == "post-production - next minor stated"


def test_parse_worklog_entry() -> None:
    parsed = parse_worklog_entry(
        {
            "id": "1234",
            "timeSpentSeconds": 7200,
            "started": "2026-03-31T09:00:00.000+0000",
            "author": {"displayName": "A User"},
        }
    )
    assert parsed is not None
    assert parsed["jira_worklog_id"] == "1234"
    assert parsed["time_spent_seconds"] == 7200
    assert parsed["author"] == "A User"


def test_first_ready_for_qa_at_uses_earliest_transition() -> None:
    ready_for_qa = first_ready_for_qa_at(
        [
            {
                "created": "2026-03-31T10:00:00.000+0000",
                "items": [{"field": "status", "toString": "Ready for test"}],
            },
            {
                "created": "2026-03-31T09:00:00.000+0000",
                "items": [{"field": "status", "toString": "Ready for QA"}],
            },
        ],
        ["Ready for QA", "Ready for test"],
    )
    assert ready_for_qa == datetime(2026, 3, 31, 9, 0, tzinfo=timezone.utc)


def test_lookback_from_returns_utc_midnight_timestamp() -> None:
    lookback = _lookback_from(14)
    assert lookback.tzinfo == timezone.utc
    assert lookback.hour == 0
    assert lookback.minute == 0
    assert lookback.second == 0


def test_build_bug_jql_uses_updated_window_and_excluded_projects() -> None:
    lookback = datetime(2026, 4, 1, tzinfo=timezone.utc)
    jql = _build_bug_jql(lookback, ["INT", " OPS "])
    assert 'updated >= "2026-04-01"' in jql
    assert "created >=" not in jql
    assert 'project NOT IN ("INT","OPS")' in jql


def test_issue_changelog_histories_complete_payload() -> None:
    histories, incomplete = issue_changelog_histories_from_search_issue(
        {
            "changelog": {
                "histories": [{"created": "2026-01-01T00:00:00.000+0000", "items": []}],
                "total": 1,
            }
        }
    )
    assert len(histories) == 1
    assert incomplete is False


def test_issue_changelog_histories_truncated_requests_full_fetch() -> None:
    histories, incomplete = issue_changelog_histories_from_search_issue(
        {"changelog": {"histories": [{"id": "1"}], "total": 50}}
    )
    assert len(histories) == 1
    assert incomplete is True


def test_issue_changelog_histories_missing_requests_full_fetch() -> None:
    histories, incomplete = issue_changelog_histories_from_search_issue({"fields": {}})
    assert histories == []
    assert incomplete is True


def test_upsert_invalid_jira_created_has_no_synthetic_timestamp() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)
    with maker() as db:
        db.add(
            ProductionBug(
                id=1,
                jira_key="BUG-1",
                healthy=True,
                jira_created_at_valid=True,
                created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            )
        )
        db.commit()
        bug = _upsert_production_bug(
            db,
            issue_key="BUG-1",
            fields={
                "created": "not-a-date",
                "issuetype": {"name": "Bug"},
                "summary": "Example",
            },
            health=HealthResult(True, "post-production", [], []),
            ready_for_qa_at=None,
            total_worklog_seconds=0,
        )
        db.commit()
        assert bug.jira_created_at_valid is False
        assert bug.created_at is None
        assert bug.mttr_minutes is None
        assert bug.healthmemo is not None
        assert "invalid or missing Jira created" in bug.healthmemo


def test_health_higher_fix_version_rescues_plunet_only_customer() -> None:
    result = evaluate_issue_health(
        issue_type="Bug",
        parent_type=None,
        parent_summary=None,
        affects_versions=["10.0.0"],
        fix_versions=["10.1.0"],
        indicator_cf10114=None,
        customer_names=["Plunet Internal"],
        parent_affects_versions=[],
        parent_fix_versions=[],
        parent_indicator_cf10114=None,
        parent_customer_names=[],
    )
    assert result.healthy is True
    assert result.healthmemo == "post-production due to higher fix_version"


def test_jira_parse_dt_normalizes_legacy_offset_without_colon() -> None:
    """Jira sometimes returns +0000 instead of +00:00."""
    parsed = _parse_dt("2026-04-01T12:00:00.000+0000")
    assert parsed is not None
    assert parsed.tzinfo == timezone.utc


def test_to_string_list_and_extract_named_values() -> None:
    assert _to_string_list(None) == []
    assert _to_string_list(["  a  ", "", None]) == ["a"]
    assert _extract_named_values(None) == []
    assert _extract_named_values([{"name": "  x  "}, {"foo": 1}]) == ["x"]


def test_parse_semver_and_max_semver() -> None:
    assert _parse_semver("not semver") is None
    assert _parse_semver("v10.2.3") == (10, 2, 3)
    assert _max_semver(["10.0.0", "v10.1.0", "bad"]) == (10, 1, 0)


def test_has_next_minor_marker() -> None:
    assert _has_next_minor_marker(["Next Minor - please branch from MASTER"])
    assert not _has_next_minor_marker(["10.0.0"])


def test_is_retryable_http_exception_jira() -> None:
    req = httpx.Request("GET", "https://jira.example")
    assert _is_retryable_http_exception(
        httpx.HTTPStatusError("x", request=req, response=httpx.Response(503, request=req))
    )
    assert not _is_retryable_http_exception(
        httpx.HTTPStatusError("x", request=req, response=httpx.Response(400, request=req))
    )


def test_jira_client_uses_basic_auth_when_user_email_set() -> None:
    client = JiraBugsClient(
        "https://jira.example",
        "api-token",
        user_email="user@atlassian.test",
    )
    try:
        assert isinstance(client.client.auth, httpx.BasicAuth)
        assert "Authorization" not in client.client.headers
    finally:
        client.close()


def test_jira_client_uses_bearer_when_no_user_email() -> None:
    client = JiraBugsClient("https://jira.example", "oauth-access")
    try:
        assert client.client.auth is None
        assert client.client.headers.get("Authorization") == "Bearer oauth-access"
    finally:
        client.close()


def test_jira_search_bugs_follows_next_page_token() -> None:
    client = JiraBugsClient("https://jira.example", "tok")
    pages = [
        {"issues": [{"key": "A-1", "fields": {}}], "nextPageToken": "t2"},
        {"issues": [{"key": "A-2", "fields": {}}], "nextPageToken": None},
    ]
    n = {"i": 0}

    def fake_get(_url: str, *, params: dict[str, object] | None = None) -> object:
        idx = n["i"]
        n["i"] += 1
        return pages[idx]

    try:
        client._get_json = fake_get  # type: ignore[method-assign]
        issues = client.search_bugs(jql="project = X", fields=["summary"], max_results=50)
    finally:
        client.close()
    assert [i["key"] for i in issues] == ["A-1", "A-2"]


def test_jira_list_worklogs_paginates() -> None:
    client = JiraBugsClient("https://jira.example", "tok")

    def fake_get(url: str, *, params: dict[str, object] | None = None) -> object:
        assert params is not None
        if "worklog" in url:
            start = int(params.get("startAt", 0))
            if start == 0:
                return {
                    "worklogs": [
                        {
                            "id": "1",
                            "timeSpentSeconds": 60,
                            "started": "2026-01-01T10:00:00.000+0000",
                            "author": {"displayName": "A"},
                        }
                    ],
                    "total": 2,
                    "maxResults": 1,
                }
            return {
                "worklogs": [
                    {
                        "id": "2",
                        "timeSpentSeconds": 120,
                        "started": "2026-01-02T10:00:00.000+0000",
                        "author": {"displayName": "B"},
                    }
                ],
                "total": 2,
                "maxResults": 1,
            }
        return {}

    try:
        client._get_json = fake_get  # type: ignore[method-assign]
        logs = client.list_issue_worklogs("X-1", max_results=1)
    finally:
        client.close()
    assert [w["id"] for w in logs] == ["1", "2"]


def test_jira_list_changelog_paginates() -> None:
    client = JiraBugsClient("https://jira.example", "tok")

    def fake_get(url: str, *, params: dict[str, object] | None = None) -> object:
        assert params is not None
        start = int(params.get("startAt", 0))
        if start == 0:
            return {"values": [{"id": "h1"}], "total": 2, "maxResults": 1}
        return {"values": [{"id": "h2"}], "total": 2, "maxResults": 1}

    try:
        client._get_json = fake_get  # type: ignore[method-assign]
        hist = client.list_issue_changelog("X-1", max_results=1)
    finally:
        client.close()
    assert [h["id"] for h in hist] == ["h1", "h2"]


def test_jira_get_issue_returns_none_for_non_dict() -> None:
    client = JiraBugsClient("https://jira.example", "tok")

    def fake_get(*_a: object, **_k: object) -> object:
        return []

    try:
        client._get_json = fake_get  # type: ignore[method-assign]
        assert client.get_issue("X-1", fields=["summary"]) is None
    finally:
        client.close()


def test_parse_worklog_entry_rejects_invalid_payload() -> None:
    assert parse_worklog_entry({}) is None
    assert parse_worklog_entry({"id": "", "timeSpentSeconds": 1}) is None
    assert parse_worklog_entry({"id": "1", "timeSpentSeconds": "x"}) is None


def test_sync_issue_worklogs_removes_entries_not_in_payload() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with maker() as db:
        db.add(
            ProductionBug(
                id=1,
                jira_key="BUG-WL",
                healthy=True,
                jira_created_at_valid=True,
                created_at=t,
            )
        )
        db.flush()
        db.add(
            IssueWorklog(
                id=10,
                bug_id=1,
                jira_worklog_id="gone",
                author="x",
                started=t,
                time_spent_seconds=1,
            )
        )
        db.add(
            IssueWorklog(
                id=11,
                bug_id=1,
                jira_worklog_id="keep",
                author="old",
                started=t,
                time_spent_seconds=2,
            )
        )
        db.commit()
        _sync_issue_worklogs(
            db,
            bug_id=1,
            parsed_worklogs=[
                {
                    "jira_worklog_id": "keep",
                    "author": "new",
                    "started": t,
                    "time_spent_seconds": 99,
                }
            ],
        )
        db.commit()
        ids = set(db.scalars(select(IssueWorklog.jira_worklog_id)).all())
        wl_keep = db.scalars(
            select(IssueWorklog).where(IssueWorklog.jira_worklog_id == "keep")
        ).one()
    assert ids == {"keep"}
    assert wl_keep.author == "new"
    assert wl_keep.time_spent_seconds == 99
