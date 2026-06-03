from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.jira_analytics.allocation.allocation_service import rebuild_monthly_allocation
from app.jira_analytics.feature_hours_service import ROW_OTHER_MISC, build_feature_hours_matrix
from app.jira_analytics.models import (
    AllocationRoleRule,
    JiraFeatureMembership,
    JiraFeatureRoot,
    JiraIssue,
    JiraIssueDetail,
    JiraProject,
    JiraUser,
    JiraUserRoleAssignment,
    JiraWorklog,
    MonthlyTopicEffortBase,
)
from app.jira_analytics.project_scope import (
    EXCLUDED_PROJECT_KEYS,
    allowed_issue_ids_subquery,
    is_excluded_project_key,
)
from app.jira_analytics.reports.reports_service import (
    feature_lifecycle,
    idea_aging,
    promised_vs_actual,
    roadmap_reliability,
    workflow_thrashing,
)
from app.jira_analytics.workflow.thrash import thrash_by_issue
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


def _issue(db: Session, *, key: str, project: JiraProject) -> JiraIssue:
    issue = JiraIssue(
        jira_issue_id=f"jira-{key}",
        key=key,
        project_id=project.id,
        issue_type_name="Story",
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(issue)
    db.flush()
    return issue


def test_excluded_project_keys_constant() -> None:
    assert EXCLUDED_PROJECT_KEYS == frozenset({"ACT", "DIM", "ITS", "JIRATESTS", "PLU", "SE"})
    assert is_excluded_project_key("its")
    assert is_excluded_project_key("SE")
    assert is_excluded_project_key("plu")
    assert is_excluded_project_key("JIRATESTS")
    assert not is_excluded_project_key("BM")


def test_allowed_issue_ids_subquery_excludes_its_and_se(db: Session) -> None:
    bm = _project(db, "BM")
    its = _project(db, "ITS")
    se = _project(db, "SE")
    plu = _project(db, "PLU")
    jiratests = _project(db, "JIRATESTS")
    bm_issue = _issue(db, key="BM-1", project=bm)
    _issue(db, key="ITS-1", project=its)
    _issue(db, key="SE-1", project=se)
    _issue(db, key="PLU-1", project=plu)
    _issue(db, key="JIRATESTS-1", project=jiratests)
    db.commit()

    allowed = set(db.execute(select(allowed_issue_ids_subquery())).scalars().all())
    assert bm_issue.id in allowed
    assert len(allowed) == 1


def test_allocation_skips_excluded_project_worklogs(db: Session) -> None:
    bm = _project(db, "BM")
    its = _project(db, "ITS")
    bm_issue = _issue(db, key="BM-10", project=bm)
    its_issue = _issue(db, key="ITS-10", project=its)
    user = JiraUser(account_id="dev-1", display_name="Dev", email_address="dev@test.com")
    db.add(user)
    db.flush()
    db.add(
        AllocationRoleRule(
            role_name="Developer",
            is_direct_production_role=True,
            is_indirect_role=False,
            overhead_percentage=Decimal(0),
            allocation_scope="direct_issue",
            allocation_base="direct_production_hours",
        )
    )
    db.add(
        JiraUserRoleAssignment(
            jira_user_id=user.id,
            user_account_id=user.account_id,
            user_email=user.email_address or "",
            display_name=user.display_name or "",
            role_name="Developer",
            team_name="Alpha",
            valid_from=date(2020, 1, 1),
        )
    )
    period = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)
    for issue in (bm_issue, its_issue):
        db.add(
            JiraWorklog(
                issue_id=issue.id,
                jira_worklog_id=f"wl-{issue.key}",
                author_user_id=user.id,
                author_account_id=user.account_id,
                author_display_name=user.display_name,
                started_at=period,
                time_spent_seconds=3600,
            )
        )
    db.commit()

    result = rebuild_monthly_allocation(db)
    assert result["topic_rows"] == 1
    rows = db.execute(select(MonthlyTopicEffortBase)).scalars().all()
    assert len(rows) == 1
    assert rows[0].issue_key == "BM-10"


def test_feature_lifecycle_omits_duration_without_end(db: Session) -> None:
    bm = _project(db, "BM")
    issue = _issue(db, key="BM-OPEN", project=bm)
    db.add(
        JiraFeatureRoot(
            root_issue_id=issue.id,
            root_key="PMGT-OPEN",
            root_project_key="BM",
            detection_rule="test",
            name="Open Feature",
        )
    )
    db.commit()

    row = next(r for r in (feature_lifecycle(db).table or []) if r["feature"] == "PMGT-OPEN")
    assert row["total_duration_days"] is None
    assert row["start_to_done_days"] is None
    assert row["end_date_source"] is None


def test_feature_lifecycle_excludes_its_roots(db: Session) -> None:
    bm = _project(db, "BM")
    its = _project(db, "ITS")
    bm_issue = _issue(db, key="BM-2", project=bm)
    its_issue = _issue(db, key="ITS-2", project=its)
    db.add(
        JiraFeatureRoot(
            root_issue_id=bm_issue.id,
            root_key="PMGT-BM",
            root_project_key="BM",
            detection_rule="test",
            name="BM Feature",
        )
    )
    db.add(
        JiraFeatureRoot(
            root_issue_id=its_issue.id,
            root_key="PMGT-ITS",
            root_project_key="ITS",
            detection_rule="test",
            name="ITS Feature",
        )
    )
    db.commit()

    report = feature_lifecycle(db)
    keys = {row["feature"] for row in report.table or []}
    assert "PMGT-BM" in keys
    assert "PMGT-ITS" not in keys


def test_flow_reports_normalize_team_names_and_group_yearly_averages(db: Session) -> None:
    bm = _project(db, "BM")
    tantrum_issue = _issue(db, key="PMGT-TANTRUM", project=bm)
    tantrum_issue.created_at_jira = datetime(2024, 1, 1, tzinfo=timezone.utc)
    world_issue = _issue(db, key="PMGT-WORLD", project=bm)
    world_issue.created_at_jira = datetime(2025, 2, 1, tzinfo=timezone.utc)
    combined_world_issue = _issue(db, key="PMGT-COMBINED-WORLD", project=bm)
    combined_world_issue.created_at_jira = datetime(2026, 3, 1, tzinfo=timezone.utc)
    for issue, team_name, start, promised, actual_end in (
        (
            tantrum_issue,
            "Cosmic Coders, Tantrum",
            datetime(2024, 1, 11, tzinfo=timezone.utc),
            date(2024, 1, 20),
            datetime(2024, 1, 25, tzinfo=timezone.utc),
        ),
        (
            world_issue,
            "World",
            datetime(2025, 2, 21, tzinfo=timezone.utc),
            date(2025, 3, 1),
            datetime(2025, 2, 28, tzinfo=timezone.utc),
        ),
        (
            combined_world_issue,
            "Cosmic Coders, World",
            datetime(2026, 3, 16, tzinfo=timezone.utc),
            date(2026, 4, 1),
            datetime(2026, 4, 3, tzinfo=timezone.utc),
        ),
    ):
        db.add(
            JiraFeatureRoot(
                root_issue_id=issue.id,
                root_key=issue.key,
                root_project_key="BM",
                detection_rule="test",
                name=issue.key,
            )
        )
        db.add(
            JiraIssueDetail(
                issue_id=issue.id,
                team_name=team_name,
                actual_start=start,
                actual_end=actual_end,
                promised_delivery_date=promised,
            )
        )
    db.commit()

    lifecycle = feature_lifecycle(db, team="Team Tantrum")
    assert [row["feature"] for row in lifecycle.table or []] == ["PMGT-TANTRUM"]
    assert lifecycle.table[0]["team"] == "Cosmic Coders, Team Tantrum"
    assert lifecycle.filters["yearly_team_averages"] == [
        {
            "team": "Team Tantrum",
            "year": 2024,
            "feature_count": 1,
            "avg_elapsed_duration_days": 24.0,
            "avg_idea_to_start_days": 10.0,
            "avg_start_to_done_days": 14.0,
            "avg_total_duration_days": 24.0,
        },
        {
            "team": "Cosmic Coders",
            "year": 2024,
            "feature_count": 1,
            "avg_elapsed_duration_days": 24.0,
            "avg_idea_to_start_days": 10.0,
            "avg_start_to_done_days": 14.0,
            "avg_total_duration_days": 24.0,
        }
    ]

    idea_aging_rows = idea_aging(db).filters["yearly_team_averages"]
    assert {
        (row["team"], row["year"], row["avg_waiting_days"])
        for row in idea_aging_rows
    } == {
        ("Team Tantrum", 2024, 10.0),
        ("Cosmic Coders", 2024, 10.0),
        ("Team World", 2025, 20.0),
        ("Team World", 2026, 15.0),
        ("Cosmic Coders", 2026, 15.0),
    }
    assert [row["year"] for row in idea_aging_rows] == [2024, 2024, 2025, 2026, 2026]

    promised = promised_vs_actual(db).filters["yearly_team_averages"]
    assert {
        (row["team"], row["year"], row["avg_delay_days"])
        for row in promised
    } == {
        ("Team Tantrum", 2024, 5.0),
        ("Cosmic Coders", 2024, 5.0),
        ("Team World", 2025, -1.0),
        ("Team World", 2026, 2.0),
        ("Cosmic Coders", 2026, 2.0),
    }

    reliability_report = roadmap_reliability(db)
    reliability = reliability_report.filters["yearly_team_averages"]
    assert {
        (row["team"], row["year"], row["reliability"], row["avg_delay_days"])
        for row in reliability
    } == {
        ("Team Tantrum", 2024, 0.0, 5.0),
        ("Cosmic Coders", 2024, 0.0, 5.0),
        ("Team World", 2025, 1.0, -1.0),
        ("Team World", 2026, 0.0, 2.0),
        ("Cosmic Coders", 2026, 0.0, 2.0),
    }
    assert reliability_report.filters["summary_year"] == date.today().year
    assert reliability_report.summary == {
        "on_time": 0,
        "delayed": 1,
        "still_open": 0,
        "reliability": 0.0,
    }


def test_promised_vs_actual_uses_last_closed_member_issue(db: Session) -> None:
    bm = _project(db, "BM")
    root_issue = _issue(db, key="PMGT-1", project=bm)
    child_a = _issue(db, key="BM-1", project=bm)
    child_b = _issue(db, key="BM-2", project=bm)
    child_a.resolved_at_jira = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    child_b.resolved_at_jira = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
    db.flush()
    root = JiraFeatureRoot(
        root_issue_id=root_issue.id,
        root_key=root_issue.key,
        root_project_key="BM",
        detection_rule="test",
        name="Promised feature",
    )
    db.add(root)
    db.flush()
    db.add_all(
        [
            JiraIssueDetail(
                issue_id=root_issue.id,
                promised_delivery_date=date(2026, 6, 15),
                actual_end=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
                team_name="Team A",
            ),
            JiraFeatureMembership(
                feature_root_id=root.id,
                member_issue_id=root_issue.id,
                depth=0,
                path_issue_keys=[root_issue.key],
                inclusion_reason="test",
            ),
            JiraFeatureMembership(
                feature_root_id=root.id,
                member_issue_id=child_a.id,
                depth=1,
                path_issue_keys=[root_issue.key, child_a.key],
                inclusion_reason="test",
            ),
            JiraFeatureMembership(
                feature_root_id=root.id,
                member_issue_id=child_b.id,
                depth=1,
                path_issue_keys=[root_issue.key, child_b.key],
                inclusion_reason="test",
            ),
        ]
    )
    db.commit()

    row = promised_vs_actual(db).table[0]

    assert row["feature"] == "PMGT-1"
    assert row["feature_title"] == "Promised feature"
    assert row["actual"] == "2026-06-20"
    assert row["delay_days"] == 5


def test_promised_vs_actual_hides_rejected_roots(db: Session) -> None:
    bm = _project(db, "BM")
    active_issue = _issue(db, key="PMGT-ACTIVE", project=bm)
    rejected_issue = _issue(db, key="PMGT-REJECTED", project=bm)
    rejected_issue.status_name = "Rejected"
    for issue in (active_issue, rejected_issue):
        db.flush()
        root = JiraFeatureRoot(
            root_issue_id=issue.id,
            root_key=issue.key,
            root_project_key="BM",
            detection_rule="test",
            name=issue.key,
        )
        db.add(root)
        db.flush()
        db.add(
            JiraIssueDetail(
                issue_id=issue.id,
                promised_delivery_date=date(2026, 6, 15),
                team_name="Team A",
            )
        )
    db.commit()

    keys = {row["feature"] for row in promised_vs_actual(db).table or []}

    assert "PMGT-ACTIVE" in keys
    assert "PMGT-REJECTED" not in keys


def test_roadmap_reliability_hides_planned_rejected_and_new_statuses(
    db: Session,
) -> None:
    bm = _project(db, "BM")
    statuses = {
        "PMGT-KEEP": "In Progress",
        "PMGT-PLANNED": "planned",
        "PMGT-REJECTED": "Rejected",
        "PMGT-NEW": "New",
    }
    for key, status in statuses.items():
        issue = _issue(db, key=key, project=bm)
        issue.status_name = status
        db.flush()
        root = JiraFeatureRoot(
            root_issue_id=issue.id,
            root_key=issue.key,
            root_project_key="BM",
            detection_rule="test",
            name=issue.key,
        )
        db.add(root)
        db.flush()
        db.add(
            JiraIssueDetail(
                issue_id=issue.id,
                promised_delivery_date=date(2026, 6, 15),
                actual_end=datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc),
                team_name="Team A",
            )
        )
    db.commit()

    report = roadmap_reliability(db)

    assert {row["feature"] for row in report.table or []} == {"PMGT-KEEP"}
    assert report.summary == {
        "on_time": 1,
        "delayed": 0,
        "still_open": 0,
        "reliability": 1.0,
    }


def test_thrash_excludes_se_issues(db: Session) -> None:
    from app.jira_analytics.models import JiraIssueStatusTransition

    se = _project(db, "SE")
    bm = _project(db, "BM")
    se_issue = _issue(db, key="SE-99", project=se)
    bm_issue = _issue(db, key="BM-99", project=bm)
    now = datetime.now(timezone.utc)
    for idx, issue in enumerate((se_issue, bm_issue), start=1):
        db.add(
            JiraIssueStatusTransition(
                issue_id=issue.id,
                jira_history_id=f"hist-{idx}",
                history_item_index=0,
                from_status_name="Open",
                to_status_name="In Progress",
                changed_at=now,
            )
        )
    db.commit()

    summaries = thrash_by_issue(db)
    keys = {s.issue_key for s in summaries}
    assert "BM-99" in keys
    assert "SE-99" not in keys

    report = workflow_thrashing(db, min_score=0)
    report_keys = {row["issue_key"] for row in report.table or []}
    assert "BM-99" in report_keys
    assert "SE-99" not in report_keys


def test_feature_hours_matrix_ignores_its_worklogs(db: Session) -> None:
    bm = _project(db, "BM")
    its = _project(db, "ITS")
    bm_issue = _issue(db, key="BM-3", project=bm)
    its_issue = _issue(db, key="ITS-3", project=its)
    user = JiraUser(account_id="dev-2", display_name="Dev2", email_address="dev2@test.com")
    db.add(user)
    db.flush()
    started = datetime(2026, 5, 15, 9, 0, tzinfo=timezone.utc)
    for issue in (bm_issue, its_issue):
        db.add(
            JiraWorklog(
                issue_id=issue.id,
                jira_worklog_id=f"wl-{issue.key}",
                author_user_id=user.id,
                author_account_id=user.account_id,
                author_display_name=user.display_name,
                started_at=started,
                time_spent_seconds=7200,
            )
        )
    db.commit()

    matrix = build_feature_hours_matrix(
        db,
        settings_json={"jira_base_url": "https://jira.example.com"},
        months=1,
        anchor=date(2026, 5, 1),
    )
    other_misc = next(row for row in matrix.rows if row.row_id == ROW_OTHER_MISC)
    assert other_misc.total_hours == 2.0
