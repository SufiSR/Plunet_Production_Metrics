from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.jira_analytics.models import JiraIssue, JiraIssueStatusTransition, JiraProject
from app.jira_analytics.reports.reports_service import workflow_thrashing
from app.jira_analytics.workflow.thrash import (
    is_excluded_qa_autotest_issue,
    thrash_by_issue,
)
from app.models.base import Base


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def _project(db: Session, key: str) -> JiraProject:
    project = JiraProject(jira_project_id=f"pid-{key}", key=key, name=key)
    db.add(project)
    db.flush()
    return project


def _issue(
    db: Session,
    *,
    key: str,
    project: JiraProject,
    issue_type_name: str = "Story",
    summary: str | None = None,
) -> JiraIssue:
    issue = JiraIssue(
        jira_issue_id=f"jira-{key}",
        key=key,
        project_id=project.id,
        issue_type_name=issue_type_name,
        summary=summary,
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(issue)
    db.flush()
    return issue


def _transition(
    db: Session,
    *,
    issue: JiraIssue,
    history_id: str,
    from_status: str,
    to_status: str,
    changed_at: datetime,
) -> None:
    db.add(
        JiraIssueStatusTransition(
            issue_id=issue.id,
            jira_history_id=history_id,
            history_item_index=0,
            from_status_name=from_status,
            to_status_name=to_status,
            changed_at=changed_at,
        )
    )


def test_is_excluded_qa_autotest_issue() -> None:
    assert is_excluded_qa_autotest_issue("QA", "Run AutoTest nightly")
    assert is_excluded_qa_autotest_issue("qa", "Export TestResult summary")
    assert not is_excluded_qa_autotest_issue("QA", "Manual regression checklist")
    assert not is_excluded_qa_autotest_issue("Story", "AutoTest harness setup")


def test_thrash_excludes_qa_autotest_titles(db: Session) -> None:
    project = _project(db, "BM")
    kept = _issue(db, key="BM-1", project=project, issue_type_name="Story")
    excluded = _issue(
        db,
        key="BM-2",
        project=project,
        issue_type_name="QA",
        summary="Pipeline AutoTest failure",
    )
    now = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)
    for idx, issue in enumerate((kept, excluded), start=1):
        _transition(
            db,
            issue=issue,
            history_id=f"hist-{idx}-1",
            from_status="Open",
            to_status="In Progress",
            changed_at=now,
        )
        _transition(
            db,
            issue=issue,
            history_id=f"hist-{idx}-2",
            from_status="In Progress",
            to_status="Done",
            changed_at=now,
        )
    db.commit()

    keys = {s.issue_key for s in thrash_by_issue(db)}
    assert "BM-1" in keys
    assert "BM-2" not in keys


def test_thrash_date_filter_limits_transitions(db: Session) -> None:
    project = _project(db, "BM")
    issue = _issue(db, key="BM-10", project=project)
    _transition(
        db,
        issue=issue,
        history_id="old-1",
        from_status="Open",
        to_status="In Progress",
        changed_at=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
    )
    _transition(
        db,
        issue=issue,
        history_id="old-2",
        from_status="In Progress",
        to_status="Done",
        changed_at=datetime(2024, 1, 16, 10, 0, tzinfo=timezone.utc),
    )
    _transition(
        db,
        issue=issue,
        history_id="new-1",
        from_status="Done",
        to_status="In Progress",
        changed_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
    )
    db.commit()

    all_time = thrash_by_issue(db)
    assert len(all_time) == 1
    assert all_time[0].status_changes == 3

    recent = thrash_by_issue(
        db,
        date_from=date(2026, 1, 1),
        date_to=date(2026, 12, 31),
    )
    assert len(recent) == 1
    assert recent[0].status_changes == 1
    assert recent[0].reopens == 1


def test_workflow_thrashing_includes_summary(db: Session) -> None:
    project = _project(db, "BM")
    issue = _issue(db, key="BM-20", project=project, summary="Flaky deploy pipeline")
    _transition(
        db,
        issue=issue,
        history_id="hist-20",
        from_status="Open",
        to_status="In Progress",
        changed_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
    )
    db.commit()

    report = workflow_thrashing(db, min_score=0)
    row = next(row for row in report.table or [] if row["issue_key"] == "BM-20")
    assert row["summary"] == "Flaky deploy pipeline"
