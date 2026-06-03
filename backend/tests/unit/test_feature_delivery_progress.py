from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.jira_analytics.feature_delivery_progress import (
    _ImplementerBucket,
    _classify_implementer_status,
    compute_delivery_progress,
    delivery_progress_by_root_issue_id,
)
from app.jira_analytics.feature_hours_service import build_feature_hours_matrix
from app.jira_analytics.models import (
    JiraFeatureMembership,
    JiraFeatureRoot,
    JiraIssue,
    JiraIssueDetail,
    JiraIssueRelation,
    JiraProject,
)
from app.models.base import Base


def test_classify_implementer_status_buckets() -> None:
    assert _classify_implementer_status("Done", "done") == _ImplementerBucket.DONE
    assert _classify_implementer_status("In Progress", "indeterminate") == _ImplementerBucket.IN_PROGRESS
    assert _classify_implementer_status("Ready for development", "new") == (
        _ImplementerBucket.BEFORE_IN_PROGRESS
    )
    assert _classify_implementer_status("Test", "indeterminate") == _ImplementerBucket.IN_PROGRESS


def test_compute_delivery_progress_rules() -> None:
    assert compute_delivery_progress([]) is None
    assert compute_delivery_progress([_ImplementerBucket.DONE, _ImplementerBucket.DONE]) == "Done"
    assert (
        compute_delivery_progress(
            [_ImplementerBucket.BEFORE_IN_PROGRESS, _ImplementerBucket.BEFORE_IN_PROGRESS]
        )
        == "In preparation"
    )
    assert (
        compute_delivery_progress(
            [_ImplementerBucket.BEFORE_IN_PROGRESS, _ImplementerBucket.IN_PROGRESS]
        )
        == "In progress"
    )
    assert (
        compute_delivery_progress([_ImplementerBucket.DONE, _ImplementerBucket.BEFORE_IN_PROGRESS])
        == "In progress"
    )


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)
    return maker()


def test_delivery_progress_from_implemented_by_links() -> None:
    db = _session()
    project = JiraProject(jira_project_id="1", key="PMGT", name="PMGT")
    db.add(project)
    db.flush()

    root = JiraIssue(
        jira_issue_id="100",
        key="PMGT-1",
        project_id=project.id,
        issue_type_name="Idea",
        summary="Feature",
        last_seen_at=datetime.now(timezone.utc),
    )
    todo = JiraIssue(
        jira_issue_id="101",
        key="BM-1",
        project_id=project.id,
        issue_type_name="Epic",
        summary="Todo epic",
        status_name="Ready to start",
        status_category_key="new",
        last_seen_at=datetime.now(timezone.utc),
    )
    active = JiraIssue(
        jira_issue_id="102",
        key="BM-2",
        project_id=project.id,
        issue_type_name="Bug",
        summary="Active bug",
        status_name="In Progress",
        status_category_key="indeterminate",
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add_all([root, todo, active])
    db.flush()
    db.add(
        JiraIssueRelation(
            source_issue_id=root.id,
            target_issue_id=todo.id,
            target_key=todo.key,
            relation_source="issue_link",
            link_type_name="Polaris work item link",
            direction="inward",
            inward_description="is implemented by",
            is_feature_membership_edge=True,
        )
    )
    db.add(
        JiraIssueRelation(
            source_issue_id=root.id,
            target_issue_id=active.id,
            target_key=active.key,
            relation_source="issue_link",
            link_type_name="Polaris work item link",
            direction="inward",
            inward_description="is implemented by",
            is_feature_membership_edge=True,
        )
    )
    db.add(
        JiraFeatureRoot(
            root_issue_id=root.id,
            root_key=root.key,
            root_project_key="PMGT",
            root_issue_type_name="Idea",
            detection_rule="test",
            active=True,
            name=root.summary,
        )
    )
    db.commit()

    assert delivery_progress_by_root_issue_id(db, [root.id]) == {root.id: "In progress"}

    db.add(
        JiraIssueDetail(
            issue_id=root.id,
            delivery_status="In preparation",
        )
    )
    db.add(
        JiraFeatureMembership(
            feature_root_id=db.execute(select(JiraFeatureRoot)).scalar_one().id,
            member_issue_id=root.id,
            depth=0,
            path_issue_keys=[root.key],
            inclusion_reason="root",
        )
    )
    db.commit()

    matrix = build_feature_hours_matrix(db, settings_json={}, months=1)
    feature_row = next(row for row in matrix.rows if row.row_type == "feature")
    assert feature_row.delivery_progress == "In progress"
