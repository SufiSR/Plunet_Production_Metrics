from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.jira_analytics.allocation.role_mapping import allocation_role_for_worklog_role
from app.jira_analytics.models import JiraUser, JiraUserRoleAssignment
from app.models.base import Base
from datetime import date as date_type
from app.models.issue_worklog import IssueWorklog
from app.models.merge_request import MergeRequest
from app.models.production_bug import ProductionBug
from app.models.repository import Repository
from app.models.release import Release
from app.services.release_worklog_hours_service import build_release_worklog_hours_response


def _seed_worklog_role_assignments(db: Session, assignments: list[dict[str, str]]) -> None:
    for item in assignments:
        account_id = (item.get("jira_account_id") or "").strip() or None
        author = (item.get("author") or "").strip() or None
        role_key = (item.get("role") or "").strip()
        team = (item.get("team") or "").strip() or None
        if not account_id and not author:
            continue
        if account_id:
            user = JiraUser(
                account_id=account_id,
                display_name=author or account_id,
                email_address=f"{account_id}@test.local",
            )
        else:
            synthetic = author.lower().replace(" ", ".")
            user = JiraUser(
                account_id=f"author:{synthetic}",
                display_name=author,
                email_address=f"{synthetic}@test.local",
            )
        db.add(user)
        db.flush()
        db.add(
            JiraUserRoleAssignment(
                jira_user_id=user.id,
                user_account_id=user.account_id if account_id else None,
                user_email=user.email_address or "",
                display_name=user.display_name or "",
                role_name=allocation_role_for_worklog_role(role_key),
                team_name=team,
                valid_from=date_type(2020, 1, 1),
            )
        )
    db.flush()


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


def test_build_release_worklog_hours_aggregates_role_and_team_and_excludes_reporting_users() -> None:
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    settings: dict = {}
    with _session() as db:
        _seed_worklog_role_assignments(
            db,
            [
                {"jira_account_id": "u-pm", "role": "pm", "team": "TeamA"},
                {"jira_account_id": "u-dev", "role": "dev", "team": "TeamA"},
                {"jira_account_id": "u-qa", "role": "qa", "team": "TeamB"},
                {"jira_account_id": "u-excluded", "role": "dev", "team": "TeamA"},
                {"jira_account_id": "bot-id", "role": "sup", "team": "Automation"},
            ],
        )
        excluded_user = db.query(JiraUser).filter_by(account_id="u-excluded").one()
        excluded_user.reporting_excluded = True
        bot_user = db.query(JiraUser).filter_by(account_id="bot-id").one()
        bot_user.reporting_excluded = True
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
        db.add(
            MergeRequest(
                id=1,
                repository_id=1,
                gitlab_mr_id=101,
                title="Fix",
                description=None,
                author="dev",
                source_branch="feature/x",
                target_branch="main",
                created_at=t,
                first_commit_at=t,
                merged_at=t,
                jira_key="BUG-1",
                first_customer_tag="v9.1.0",
                first_customer_tag_date=t,
            )
        )
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
                IssueWorklog(
                    id=6,
                    bug_id=1,
                    jira_worklog_id="w6",
                    jira_account_id="u-excluded",
                    author="Excluded",
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
    assert out.hours_by_role.sup == 0.0
    assert out.hours_by_role.unmapped == 0.5
    by_team = {r.team: r.hours for r in out.hours_by_team}
    assert by_team["TeamA"] == 3.0
    assert by_team["TeamB"] == 1.0
    assert out.unmapped_team_hours == 0.5
    # total excludes bot: 3600+7200+3600+1800 = 16200 -> 4.5h
    assert out.total_hours == 4.5


def test_build_release_worklog_hours_falls_back_to_author_assignment_when_account_missing() -> None:
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    settings: dict = {}
    with _session() as db:
        _seed_worklog_role_assignments(
            db,
            [{"author": "Legacy User", "role": "dev", "team": "LegacyTeam"}],
        )
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
                jira_key="BUG-2",
                healthy=True,
                jira_created_at_valid=True,
                created_at=t,
            )
        )
        db.flush()
        db.add(
            Release(
                id=1,
                repository_id=1,
                tag_name="v9.2.0",
                customer_release=True,
                version_major=9,
                version_minor=2,
                version_patch=0,
                commit_sha="b" * 40,
                committed_at=t,
            )
        )
        db.flush()
        db.add(
            MergeRequest(
                id=1,
                repository_id=1,
                gitlab_mr_id=201,
                title="Legacy",
                description=None,
                author="dev",
                source_branch="feature/legacy",
                target_branch="main",
                created_at=t,
                first_commit_at=t,
                merged_at=t,
                jira_key="BUG-2",
                first_customer_tag="v9.2.0",
                first_customer_tag_date=t,
            )
        )
        db.add(
            IssueWorklog(
                id=10,
                bug_id=1,
                jira_worklog_id="w10",
                jira_account_id=None,
                author="Legacy User",
                started=t,
                time_spent_seconds=3600,
            )
        )
        db.commit()

        out = build_release_worklog_hours_response(
            db,
            repository_id=1,
            tag_name="v9.2.0",
            settings_json=settings,
        )

    assert out is not None
    assert out.hours_by_role.dev == 1.0
    assert out.hours_by_role.sup == 0.0
    by_team = {r.team: r.hours for r in out.hours_by_team}
    assert by_team["LegacyTeam"] == 1.0


def test_build_release_worklog_hours_uses_mr_linked_jira_not_bugrelease() -> None:
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
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
        db.add_all(
            [
                ProductionBug(
                    id=1,
                    jira_key="BUG-MR",
                    healthy=True,
                    jira_created_at_valid=True,
                    created_at=t,
                ),
                ProductionBug(
                    id=2,
                    jira_key="BUG-OTHER",
                    healthy=True,
                    jira_created_at_valid=True,
                    created_at=t,
                ),
            ]
        )
        db.flush()
        db.add(
            Release(
                id=1,
                repository_id=1,
                tag_name="v10.25.2",
                customer_release=True,
                version_major=10,
                version_minor=25,
                version_patch=2,
                commit_sha="c" * 40,
                committed_at=t,
            )
        )
        db.add_all(
            [
                MergeRequest(
                    id=1,
                    repository_id=1,
                    gitlab_mr_id=301,
                    title="MR-linked",
                    description=None,
                    author="dev",
                    source_branch="feature/mr",
                    target_branch="main",
                    created_at=t,
                    first_commit_at=t,
                    merged_at=t,
                    jira_key="BUG-MR",
                    first_customer_tag="v10.25.2",
                    first_customer_tag_date=t,
                ),
                # Same key twice in release should not double-count worklogs.
                MergeRequest(
                    id=2,
                    repository_id=1,
                    gitlab_mr_id=302,
                    title="MR-linked-2",
                    description=None,
                    author="dev",
                    source_branch="feature/mr2",
                    target_branch="main",
                    created_at=t,
                    first_commit_at=t,
                    merged_at=t,
                    jira_key="BUG-MR",
                    first_customer_tag="v10.25.2",
                    first_customer_tag_date=t,
                ),
            ]
        )
        db.add_all(
            [
                IssueWorklog(
                    id=21,
                    bug_id=1,
                    jira_worklog_id="w21",
                    jira_account_id=None,
                    author="A",
                    started=t,
                    time_spent_seconds=1800,
                ),
                IssueWorklog(
                    id=22,
                    bug_id=2,
                    jira_worklog_id="w22",
                    jira_account_id=None,
                    author="B",
                    started=t,
                    time_spent_seconds=7200,
                ),
            ]
        )
        db.commit()

        out = build_release_worklog_hours_response(
            db,
            repository_id=1,
            tag_name="v10.25.2",
            settings_json={},
        )

    assert out is not None
    # Only BUG-MR should be counted for this tag; BUG-OTHER is not MR-linked to the tag.
    assert out.total_hours == 0.5
