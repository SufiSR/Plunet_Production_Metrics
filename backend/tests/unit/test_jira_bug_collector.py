from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.models.production_bug import ProductionBug
from app.services.jira_bug_collector import (
    HealthResult,
    _build_bug_jql,
    _lookback_from,
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
