from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.jira_analytics.data_quality import build_data_quality
from app.jira_analytics.data_quality import (
    REPORTING_EXCLUDED_USERS_WITH_WORKLOGS_CHECK_ID,
    WORKLOG_USERS_WITHOUT_ASSIGNMENT_CHECK_ID,
)
from app.jira_analytics.models import (
    JiraDataQualityUserIgnore,
    JiraIssue,
    JiraIssueDetail,
    JiraProject,
    JiraUser,
    JiraWorklog,
)
from app.models.base import Base


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return factory()


def test_data_quality_warns_on_missing_assignments_and_excluded_worklogs() -> None:
    db = _session()
    project = JiraProject(jira_project_id="1", key="BM", name="BM")
    db.add(project)
    db.flush()
    issue = JiraIssue(
        jira_issue_id="1",
        key="BM-1",
        project_id=project.id,
        issue_type_name="Story",
        last_seen_at=datetime.now(timezone.utc),
    )
    missing_assignment = JiraUser(
        account_id="missing-role",
        display_name="Missing Role",
        email_address="missing@test.com",
    )
    ignored_missing_assignment = JiraUser(
        account_id="ignored-missing-role",
        display_name="Ignored Missing Role",
        email_address="ignored.missing@test.com",
    )
    excluded = JiraUser(
        account_id="excluded",
        display_name="Excluded",
        email_address="excluded@test.com",
        reporting_excluded=True,
    )
    ignored_excluded = JiraUser(
        account_id="ignored-excluded",
        display_name="Ignored Excluded",
        email_address="ignored.excluded@test.com",
        reporting_excluded=True,
    )
    db.add_all([issue, missing_assignment, ignored_missing_assignment, excluded, ignored_excluded])
    db.flush()
    db.add_all(
        [
            JiraIssueDetail(issue_id=issue.id, team_name=None),
            JiraWorklog(
                issue_id=issue.id,
                jira_worklog_id="wl-missing",
                author_user_id=missing_assignment.id,
                author_account_id=missing_assignment.account_id,
                started_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
                time_spent_seconds=3600,
            ),
            JiraWorklog(
                issue_id=issue.id,
                jira_worklog_id="wl-ignored-missing",
                author_user_id=ignored_missing_assignment.id,
                author_account_id=ignored_missing_assignment.account_id,
                started_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
                time_spent_seconds=3600,
            ),
            JiraWorklog(
                issue_id=issue.id,
                jira_worklog_id="wl-excluded",
                author_user_id=excluded.id,
                author_account_id=excluded.account_id,
                started_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
                time_spent_seconds=3600,
            ),
            JiraWorklog(
                issue_id=issue.id,
                jira_worklog_id="wl-ignored-excluded",
                author_user_id=ignored_excluded.id,
                author_account_id=ignored_excluded.account_id,
                started_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
                time_spent_seconds=3600,
            ),
            JiraDataQualityUserIgnore(
                check_id=WORKLOG_USERS_WITHOUT_ASSIGNMENT_CHECK_ID,
                jira_user_id=ignored_missing_assignment.id,
                active=True,
            ),
            JiraDataQualityUserIgnore(
                check_id=REPORTING_EXCLUDED_USERS_WITH_WORKLOGS_CHECK_ID,
                jira_user_id=ignored_excluded.id,
                active=True,
            ),
        ]
    )
    db.commit()

    response = build_data_quality(db)
    warnings = {w.check_id: w for w in response.data_quality.warnings}

    assert warnings[WORKLOG_USERS_WITHOUT_ASSIGNMENT_CHECK_ID].count == 3
    assert warnings[WORKLOG_USERS_WITHOUT_ASSIGNMENT_CHECK_ID].ignored_count == 1
    assert warnings[REPORTING_EXCLUDED_USERS_WITH_WORKLOGS_CHECK_ID].count == 1
    assert warnings[REPORTING_EXCLUDED_USERS_WITH_WORKLOGS_CHECK_ID].ignored_count == 1
    assert "issues_missing_team" not in warnings
