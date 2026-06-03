from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.jira_analytics.allocation.allocation_service import rebuild_monthly_allocation
from app.jira_analytics.allocation.role_mapping import allocation_role_for_worklog_role
from app.jira_analytics.feature_hours_service import (
    ROW_OTHER_BUG,
    ROW_OTHER_MISC,
    build_feature_hours_matrix,
    build_feature_hours_row_drilldown,
)
from app.jira_analytics.models import (
    JiraFeatureMembership,
    JiraFeatureRoot,
    JiraIssue,
    JiraIssueDetail,
    JiraProject,
    JiraUser,
    JiraUserRoleAssignment,
    JiraWorklog,
    MonthlyAllocatedEffort,
)
from app.models.base import Base


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)
    return maker()


def _seed_matrix_fixture(db: Session) -> None:
    project = JiraProject(jira_project_id="1", key="PMGT", name="PMGT")
    db.add(project)
    db.flush()
    dev = JiraUser(account_id="acc-dev", display_name="Dev", email_address="dev@test.com")
    db.add(dev)
    db.flush()
    db.add(
        JiraUserRoleAssignment(
            jira_user_id=dev.id,
            user_account_id=dev.account_id,
            user_email=dev.email_address or "",
            display_name=dev.display_name or "",
            role_name=allocation_role_for_worklog_role("dev"),
            team_name="Alpha",
            valid_from=date_type(2020, 1, 1),
        )
    )

    feature = JiraIssue(
        jira_issue_id="100",
        key="PMGT-1",
        project_id=project.id,
        issue_type_name="Idea",
        summary="Feature A",
        self_url="https://jira.example.com/rest/api/3/issue/100",
        last_seen_at=datetime.now(timezone.utc),
    )
    epic = JiraIssue(
        jira_issue_id="101",
        key="HUB-10",
        project_id=project.id,
        issue_type_name="Epic",
        summary="Epic child",
        self_url="https://jira.example.com/rest/api/3/issue/101",
        last_seen_at=datetime.now(timezone.utc),
    )
    child = JiraIssue(
        jira_issue_id="102",
        key="HUB-11",
        project_id=project.id,
        issue_type_name="Improvement",
        summary="Child issue",
        parent_issue_id=None,
        self_url="https://jira.example.com/rest/api/3/issue/102",
        last_seen_at=datetime.now(timezone.utc),
    )
    bug = JiraIssue(
        jira_issue_id="103",
        key="BM-1",
        project_id=project.id,
        issue_type_name="Bug",
        summary="Loose bug",
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add_all([feature, epic, child, bug])
    db.flush()

    child.parent_issue_id = epic.id
    db.add_all(
        [
            JiraIssueDetail(
                issue_id=feature.id,
                start_date=datetime(2026, 1, 15, tzinfo=timezone.utc).date(),
                promised_delivery_date=datetime(2026, 6, 30, tzinfo=timezone.utc).date(),
                team_name="Alpha",
                delivery_status="In progress",
            ),
            JiraIssueDetail(
                issue_id=child.id,
                epic_link_issue_id=epic.id,
                epic_link_key=epic.key,
            ),
        ]
    )

    root = JiraFeatureRoot(
        root_issue_id=feature.id,
        root_key=feature.key,
        root_project_key="PMGT",
        root_issue_type_name="Idea",
        detection_rule="test",
        active=True,
        name=feature.summary,
    )
    db.add(root)
    db.flush()

    for member_id, depth in (
        (feature.id, 0),
        (epic.id, 1),
        (child.id, 2),
    ):
        db.add(
            JiraFeatureMembership(
                feature_root_id=root.id,
                member_issue_id=member_id,
                depth=depth,
                path_issue_keys=[feature.key],
                inclusion_reason="test",
            )
        )

    started = datetime.now(timezone.utc)

    db.add_all(
        [
            JiraWorklog(
                issue_id=child.id,
                jira_worklog_id="w1",
                time_spent_seconds=3600,
                started_at=started,
                author_account_id=dev.account_id,
                author_display_name=dev.display_name,
            ),
            JiraWorklog(
                issue_id=bug.id,
                jira_worklog_id="w2",
                time_spent_seconds=7200,
                started_at=started,
                author_account_id=dev.account_id,
                author_display_name=dev.display_name,
            ),
        ]
    )
    db.commit()
    rebuild_monthly_allocation(db)


def test_feature_hours_matrix_newest_period_first_and_metadata() -> None:
    db = _session()
    _seed_matrix_fixture(db)
    matrix = build_feature_hours_matrix(
        db,
        settings_json={"jira": {"base_url": "https://jira.example.com"}},
        months=3,
        anchor=datetime(2026, 5, 22, tzinfo=timezone.utc).date(),
    )
    assert matrix.periods == ["2026-05", "2026-04", "2026-03"]
    feature_row = next(row for row in matrix.rows if row.row_id == "PMGT-1")
    assert feature_row.label == "Feature A"
    assert feature_row.feature_name == "Feature A"
    assert feature_row.start_date == "2026-01-15"
    assert feature_row.target_end_date == "2026-06-30"
    assert feature_row.team_name == "Alpha"
    assert matrix.rows[0].row_id == "PMGT-1"
    assert matrix.rows[-1].row_id == ROW_OTHER_BUG


def test_feature_hours_matrix_sorts_by_period_cascade() -> None:
    db = _session()
    _seed_matrix_fixture(db)
    anchor = datetime(2026, 5, 22, tzinfo=timezone.utc).date()
    matrix = build_feature_hours_matrix(
        db,
        settings_json={"jira": {"base_url": "https://jira.example.com"}},
        months=2,
        anchor=anchor,
    )
    assert matrix.periods == ["2026-05", "2026-04"]

    feature_b = JiraIssue(
        jira_issue_id="200",
        key="PMGT-2",
        project_id=db.execute(select(JiraProject)).scalar_one().id,
        issue_type_name="Idea",
        summary="Feature B",
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(feature_b)
    db.flush()
    root_b = JiraFeatureRoot(
        root_issue_id=feature_b.id,
        root_key=feature_b.key,
        root_project_key="PMGT",
        root_issue_type_name="Idea",
        detection_rule="test",
        active=True,
        name=feature_b.summary,
    )
    db.add(root_b)
    db.flush()
    db.add(
        JiraFeatureMembership(
            feature_root_id=root_b.id,
            member_issue_id=feature_b.id,
            depth=0,
            path_issue_keys=[feature_b.key],
            inclusion_reason="test",
        )
    )
    may = datetime(2026, 5, 10, tzinfo=timezone.utc)
    april = datetime(2026, 4, 10, tzinfo=timezone.utc)
    db.add_all(
        [
            JiraWorklog(
                issue_id=feature_b.id,
                jira_worklog_id="w-b-may",
                time_spent_seconds=3600,
                started_at=may,
                author_account_id="acc-dev",
                author_display_name="Dev",
            ),
            JiraWorklog(
                issue_id=feature_b.id,
                jira_worklog_id="w-b-april",
                time_spent_seconds=7200,
                started_at=april,
                author_account_id="acc-dev",
                author_display_name="Dev",
            ),
        ]
    )
    db.commit()
    rebuild_monthly_allocation(db)

    matrix = build_feature_hours_matrix(
        db,
        settings_json={"jira": {"base_url": "https://jira.example.com"}},
        months=2,
        anchor=anchor,
    )
    feature_rows = [row for row in matrix.rows if row.row_type == "feature"]
    assert len(feature_rows) == 2
    # PMGT-1: 1h May; PMGT-2: 1h May, 2h April - PMGT-2 wins on the April tiebreaker.
    assert feature_rows[0].row_id == "PMGT-2"
    assert feature_rows[1].row_id == "PMGT-1"


def test_feature_hours_matrix_splits_feature_and_other_bug() -> None:
    db = _session()
    _seed_matrix_fixture(db)
    settings: dict = {}
    matrix = build_feature_hours_matrix(db, settings_json=settings, months=1)
    by_id = {row.row_id: row for row in matrix.rows}
    assert by_id["PMGT-1"].total_hours == 1.0
    assert by_id[ROW_OTHER_BUG].total_hours == 2.0
    assert matrix.periods[0] == datetime.now(timezone.utc).strftime("%Y-%m")
    feature_row = by_id["PMGT-1"]
    assert feature_row.feature_name == "Feature A"
    assert feature_row.start_date == "2026-01-15"
    assert feature_row.target_end_date == "2026-06-30"
    assert feature_row.team_name == "Alpha"
    assert feature_row.delivery_progress == "In progress"
    assert matrix.rows[0].row_id == "PMGT-1"
    assert ROW_OTHER_MISC not in by_id


def test_feature_hours_drilldown_sorts_issues_by_period_cascade() -> None:
    db = _session()
    _seed_matrix_fixture(db)
    anchor = datetime(2026, 5, 22, tzinfo=timezone.utc).date()
    may = datetime(2026, 5, 10, tzinfo=timezone.utc)
    april = datetime(2026, 4, 10, tzinfo=timezone.utc)

    project = db.execute(select(JiraProject)).scalar_one()
    heavy_may = JiraIssue(
        jira_issue_id="201",
        key="HUB-20",
        project_id=project.id,
        issue_type_name="Improvement",
        summary="Heavy in May",
        last_seen_at=datetime.now(timezone.utc),
    )
    heavy_april = JiraIssue(
        jira_issue_id="202",
        key="HUB-21",
        project_id=project.id,
        issue_type_name="Improvement",
        summary="Heavy in April",
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add_all([heavy_may, heavy_april])
    db.flush()

    root = db.execute(select(JiraFeatureRoot)).scalar_one()
    for issue_id, depth in ((heavy_may.id, 2), (heavy_april.id, 2)):
        db.add(
            JiraFeatureMembership(
                feature_root_id=root.id,
                member_issue_id=issue_id,
                depth=depth,
                path_issue_keys=[root.root_key],
                inclusion_reason="test",
            )
        )
    db.add_all(
        [
            JiraWorklog(
                issue_id=heavy_may.id,
                jira_worklog_id="w-may-heavy",
                time_spent_seconds=10_800,
                started_at=may,
                author_account_id="acc-dev",
                author_display_name="Dev",
            ),
            JiraWorklog(
                issue_id=heavy_april.id,
                jira_worklog_id="w-april-heavy",
                time_spent_seconds=14_400,
                started_at=april,
                author_account_id="acc-dev",
                author_display_name="Dev",
            ),
        ]
    )
    db.commit()
    rebuild_monthly_allocation(db)

    payload = build_feature_hours_row_drilldown(
        db,
        settings_json={"jira": {"base_url": "https://jira.example.com"}},
        row_id="PMGT-1",
        months=2,
        anchor=anchor,
    )
    assert payload is not None
    other_section = next(
        section for section in payload.sections if section.epic_summary == "Other linked issues"
    )
    assert [issue.issue_key for issue in other_section.issues] == ["HUB-20", "HUB-21"]


def test_feature_hours_drilldown_groups_under_epic() -> None:
    db = _session()
    _seed_matrix_fixture(db)
    payload = build_feature_hours_row_drilldown(
        db,
        settings_json={"jira": {"base_url": "https://jira.example.com"}},
        row_id="PMGT-1",
        months=1,
    )
    assert payload is not None
    assert payload.row_id == "PMGT-1"
    assert payload.row_type == "feature"
    assert any(section.epic_key == "HUB-10" for section in payload.sections)
    epic_section = next(section for section in payload.sections if section.epic_key == "HUB-10")
    assert epic_section.epic_url == "https://jira.example.com/browse/HUB-10"
    child = next(issue for issue in epic_section.issues if issue.issue_key == "HUB-11")
    assert child.issue_url == "https://jira.example.com/browse/HUB-11"


def test_other_bug_drilldown_lists_unassigned_issues() -> None:
    db = _session()
    _seed_matrix_fixture(db)
    payload = build_feature_hours_row_drilldown(
        db,
        settings_json={"jira": {"base_url": "https://jira.example.com"}},
        row_id=ROW_OTHER_BUG,
        months=1,
    )
    assert payload is not None
    assert payload.row_type == "other_bug"
    keys = [issue.issue_key for section in payload.sections for issue in section.issues]
    assert keys == ["BM-1"]
    assert payload.sections[0].issues[0].issue_url == "https://jira.example.com/browse/BM-1"


def test_other_drilldown_keeps_issue_less_allocated_overhead() -> None:
    db = _session()
    _seed_matrix_fixture(db)
    period = datetime.now(timezone.utc).date().replace(day=1)
    db.add(
        MonthlyAllocatedEffort(
            period_month=period,
            topic_type="tech_support",
            team_name="Alpha",
            source_user_email="po@test.com",
            source_display_name="Product Owner",
            source_role_name="Product Owner",
            allocation_kind="indirect_allocated",
            hours=Decimal("3"),
            rule_snapshot_json={},
        )
    )
    db.commit()

    payload = build_feature_hours_row_drilldown(
        db,
        settings_json={"jira": {"base_url": "https://jira.example.com"}},
        row_id=ROW_OTHER_MISC,
        months=1,
    )

    assert payload is not None
    assert payload.row_type == "other_misc"
    section = next(
        item for item in payload.sections if item.epic_summary == "Allocated overhead without issue"
    )
    issue = section.issues[0]
    assert issue.issue_key == f"{ROW_OTHER_MISC}-allocated-overhead-without-issue"
    assert issue.summary == "Other misc allocated overhead without issue attribution"
    assert issue.total_hours == 3.0
