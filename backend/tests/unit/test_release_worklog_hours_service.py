from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.models.repository import Repository
from app.models.bug_release import BugRelease
from app.models.issue_worklog import IssueWorklog
from app.models.production_bug import ProductionBug
from app.models.release import Release
from app.services.release_worklog_hours_service import build_release_worklog_hours_response


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)
    return maker()


def test_build_release_worklog_hours_response_none_when_no_release() -> None:
    with _session() as db:
        out = build_release_worklog_hours_response(
            db,
            repository_id=1,
            tag_name="v1.0.0",
            settings_json={},
        )
    assert out is None


def test_build_release_worklog_hours_aggregates_role_and_team_and_denylist() -> None:
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    settings = {
        "jira": {
            "jira_worklog_author_denylist": ["bot-id"],
            "jira_worklog_user_assignments": [
                {"jira_account_id": "u-pm", "role": "pm", "team": "TeamA"},
                {"jira_account_id": "u-dev", "role": "dev", "team": "TeamA"},
                {"jira_account_id": "u-qa", "role": "qa", "team": "TeamB"},
            ],
        },
    }
    with _session() as db:
        db.add(
            Repository(
                id=1,
                gitlab_id=1,
                name="app",
                path="g/app",
                default_branch="main",
                active=True,
            )
        )
        db.flush()
        db.add(
            ProductionBug(
                id=1,
                jira_key="BUG-1",
                healthy=True,
                jira_created_at_valid=True,
                created_at=t,
            )
        )
        db.flush()
        rel = Release(
            id=1,
            repository_id=1,
            tag_name="v9.1.0",
            customer_release=True,
            version_major=9,
            version_minor=1,
            version_patch=0,
            commit_sha="a" * 40,
            committed_at=t,
        )
        db.add(rel)
        db.flush()
        db.add(BugRelease(bug_id=1, release_id=1))
        db.add_all(
            [
                IssueWorklog(
                    id=1,
                    bug_id=1,
                    jira_worklog_id="w1",
                    jira_account_id="u-pm",
                    author="PM",
                    started=t,
                    time_spent_seconds=3600,
                ),
                IssueWorklog(
                    id=2,
                    bug_id=1,
                    jira_worklog_id="w2",
                    jira_account_id="u-dev",
                    author="Dev",
                    started=t,
                    time_spent_seconds=7200,
                ),
                IssueWorklog(
                    id=3,
                    bug_id=1,
                    jira_worklog_id="w3",
                    jira_account_id="u-qa",
                    author="QA",
                    started=t,
                    time_spent_seconds=3600,
                ),
                IssueWorklog(
                    id=4,
                    bug_id=1,
                    jira_worklog_id="w4",
                    jira_account_id=None,
                    author="Ghost",
                    started=t,
                    time_spent_seconds=1800,
                ),
                IssueWorklog(
                    id=5,
                    bug_id=1,
                    jira_worklog_id="w5",
                    jira_account_id="bot-id",
                    author="Bot",
                    started=t,
                    time_spent_seconds=9999,
                ),
            ]
        )
        db.commit()

        out = build_release_worklog_hours_response(
            db,
            repository_id=1,
            tag_name="v9.1.0",
            settings_json=settings,
        )

    assert out is not None
    assert out.hours_by_role.pm == 1.0
    assert out.hours_by_role.dev == 2.0
    assert out.hours_by_role.qa == 1.0
    assert out.hours_by_role.unmapped == 0.5
    by_team = {r.team: r.hours for r in out.hours_by_team}
    assert by_team["TeamA"] == 3.0
    assert by_team["TeamB"] == 1.0
    assert out.unmapped_team_hours == 0.5
    # total excludes bot: 3600+7200+3600+1800 = 16200 -> 4.5h
    assert out.total_hours == 4.5
