from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.jira_analytics.models import (
    JiraIssue,
    JiraProject,
    JiraProjectWorkflowMapping,
    JiraWorkflow,
)
from app.jira_analytics.workflow.status_intervals import StatusInterval
from app.jira_analytics.workflow.status_waiting import (
    aggregate_status_waiting_points,
    build_status_waiting_groups,
    clip_interval_seconds,
)
from app.jira_analytics.workflow.workflow_normalization import canonical_status_name
from app.jira_analytics.workflow.workflow_resolution import resolve_workflow_ids_for_issues
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


def _interval(
    *,
    issue_id: int,
    project_key: str,
    issue_type_name: str,
    status_name: str,
    start: datetime,
    end: datetime,
) -> StatusInterval:
    duration = (end - start).total_seconds()
    return StatusInterval(
        issue_id=issue_id,
        issue_key=f"{project_key}-{issue_id}",
        project_key=project_key,
        issue_type_name=issue_type_name,
        status_name=status_name,
        interval_start=start,
        interval_end=end,
        duration_seconds=duration,
    )


def _seed_story_workflow(db: Session) -> tuple[JiraProject, JiraIssue, JiraWorkflow]:
    project = JiraProject(jira_project_id="100", key="BM", name="Business Manager")
    db.add(project)
    db.flush()
    workflow = JiraWorkflow(
        jira_entity_id="wf-story",
        name="BM Story Flow",
        status_order_json=["Backlog", "In Progress"],
    )
    db.add(workflow)
    db.flush()
    db.add(
        JiraProjectWorkflowMapping(
            project_id=project.id,
            issue_type_id="story-type",
            workflow_id=workflow.id,
            issue_type_name="Story",
        )
    )
    issue = JiraIssue(
        jira_issue_id="200",
        key="BM-1",
        project_id=project.id,
        issue_type_id="story-type",
        issue_type_name="Story",
        priority_name="Medium",
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(issue)
    db.flush()
    return project, issue, workflow


def test_canonical_status_name_strips_markers() -> None:
    assert canonical_status_name("In Arbeit (!)") == "In Arbeit"


def test_clip_interval_seconds_respects_date_range() -> None:
    interval = _interval(
        issue_id=1,
        project_key="BM",
        issue_type_name="Story",
        status_name="Open",
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 10, tzinfo=timezone.utc),
    )
    clipped = clip_interval_seconds(
        interval,
        date_from=date(2026, 1, 5),
        date_to=date(2026, 1, 6),
    )
    assert clipped == pytest.approx(2 * 86400.0, rel=1e-5)


def test_resolve_workflow_from_project_mapping(db: Session) -> None:
    _, issue, workflow = _seed_story_workflow(db)
    db.commit()
    resolved = resolve_workflow_ids_for_issues(db, {issue.id})
    assert resolved[issue.id] == workflow.id


def test_build_status_waiting_groups_by_jira_workflow(db: Session) -> None:
    _, issue, workflow = _seed_story_workflow(db)
    db.commit()
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    mid = datetime(2026, 1, 5, tzinfo=timezone.utc)
    end = datetime(2026, 1, 10, tzinfo=timezone.utc)
    intervals = [
        _interval(
            issue_id=issue.id,
            project_key="BM",
            issue_type_name="Story",
            status_name="Backlog",
            start=start,
            end=mid,
        ),
        _interval(
            issue_id=issue.id,
            project_key="BM",
            issue_type_name="Story",
            status_name="In Progress",
            start=mid,
            end=end,
        ),
        _interval(
            issue_id=issue.id,
            project_key="BM",
            issue_type_name="Story",
            status_name="Done",
            start=mid,
            end=end,
        ),
    ]
    groups = build_status_waiting_groups(
        db,
        intervals,
        date_from=None,
        date_to=None,
        project_keys=None,
        issue_type_family=None,
        workflow_name=None,
    )
    assert len(groups) == 1
    assert groups[0]["label"] == workflow.name
    assert [row["status"] for row in groups[0]["rows"]] == ["Backlog", "In Progress"]


def test_aggregate_status_waiting_points_totals_repeated_visits_per_issue() -> None:
    workflow = JiraWorkflow(
        jira_entity_id="wf-standard",
        name="Standard Plunet Workflow",
        status_order_json=["Backlog"],
    )
    rows, _columns = aggregate_status_waiting_points(
        [
            {
                "issue_id": 1,
                "issue_type": "Analysis",
                "status": "Backlog",
                "priority": "Critical",
                "days": 1.0,
            },
            {
                "issue_id": 1,
                "issue_type": "Analysis",
                "status": "Backlog",
                "priority": "Critical",
                "days": 3.0,
            },
            {
                "issue_id": 2,
                "issue_type": "Analysis",
                "status": "Backlog",
                "priority": "Critical",
                "days": 8.0,
            },
        ],
        workflow=workflow,
        selected_issue_types={"Analysis"},
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["unique_issue_count"] == 2
    assert row["median_by_priority"]["Critical"] == 6.0
    assert row["average_by_priority"]["Critical"] == 6.0
    assert row["average_days_all_priorities"] == 6.0


def test_bug_subtask_uses_same_workflow_mapping(db: Session) -> None:
    project = JiraProject(jira_project_id="101", key="CRM", name="CRM")
    db.add(project)
    db.flush()
    workflow = JiraWorkflow(
        jira_entity_id="wf-bug",
        name="CRM Bug Flow",
        status_order_json=["Open"],
    )
    db.add(workflow)
    db.flush()
    for issue_type_id, issue_type_name in (
        ("bug-type", "Bug"),
        ("bug-sub-type", "Bug Sub-task"),
    ):
        db.add(
            JiraProjectWorkflowMapping(
                project_id=project.id,
                issue_type_id=issue_type_id,
                workflow_id=workflow.id,
                issue_type_name=issue_type_name,
            )
        )
    bug = JiraIssue(
        jira_issue_id="301",
        key="CRM-1",
        project_id=project.id,
        issue_type_id="bug-type",
        issue_type_name="Bug",
        last_seen_at=datetime.now(timezone.utc),
    )
    sub = JiraIssue(
        jira_issue_id="302",
        key="CRM-2",
        project_id=project.id,
        issue_type_id="bug-sub-type",
        issue_type_name="Bug Sub-task",
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add_all([bug, sub])
    db.commit()
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 2, tzinfo=timezone.utc)
    intervals = [
        _interval(
            issue_id=bug.id,
            project_key="CRM",
            issue_type_name="Bug",
            status_name="Open",
            start=start,
            end=end,
        ),
        _interval(
            issue_id=sub.id,
            project_key="CRM",
            issue_type_name="Bug Sub-task",
            status_name="Open",
            start=start,
            end=end,
        ),
    ]
    groups = build_status_waiting_groups(
        db,
        intervals,
        date_from=None,
        date_to=None,
        project_keys=None,
        issue_type_family=None,
        workflow_name=None,
    )
    assert len(groups) == 1
    assert groups[0]["workflow_name"] == "CRM Bug Flow"
