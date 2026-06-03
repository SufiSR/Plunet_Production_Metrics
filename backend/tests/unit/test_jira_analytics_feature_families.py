from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.jira_analytics.feature_family_hours_service import build_feature_family_hours_matrix
from app.jira_analytics.models import (
    JiraFeatureFamily,
    JiraFeatureFamilyMember,
    JiraFeatureRoot,
    JiraIssue,
    JiraIssueDetail,
    JiraProject,
    MonthlyAllocatedEffort,
)
from app.models import Base


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session)()


def _seed_root(
    db: Session,
    *,
    key: str,
    summary: str,
    start: date,
    target: date,
    progress: str,
    team: str,
) -> JiraFeatureRoot:
    project = db.query(JiraProject).filter_by(key="PMGT").one_or_none()
    if project is None:
        project = JiraProject(jira_project_id="project-pmgt", key="PMGT", name="PMGT")
        db.add(project)
        db.flush()
    issue = JiraIssue(
        jira_issue_id=f"issue-{key}",
        key=key,
        project_id=project.id,
        issue_type_name="Idea",
        summary=summary,
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(issue)
    db.flush()
    db.add(
        JiraIssueDetail(
            issue_id=issue.id,
            start_date=start,
            promised_delivery_date=target,
            delivery_status=progress,
            team_name=team,
        )
    )
    root = JiraFeatureRoot(
        root_issue_id=issue.id,
        root_key=key,
        root_project_key="PMGT",
        root_issue_type_name="Idea",
        name=summary,
        detection_rule="unit-test",
        active=True,
    )
    db.add(root)
    db.flush()
    return root


def _add_hours(db: Session, root: JiraFeatureRoot, *, hours: Decimal, team: str) -> None:
    db.add(
        MonthlyAllocatedEffort(
            period_month=date(2026, 5, 1),
            topic_type="feature",
            feature_root_id=root.id,
            feature_key=root.root_key,
            feature_name=root.name,
            issue_id=root.root_issue_id,
            issue_key=root.root_key,
            team_name=team,
            source_user_email="dev@example.com",
            source_display_name="Dev",
            source_role_name="Developer",
            allocation_kind="direct_worklog",
            hours=hours,
            rule_snapshot_json={},
        )
    )


def test_feature_family_matrix_rolls_up_dates_progress_teams_and_hours() -> None:
    db = _session()
    first = _seed_root(
        db,
        key="PMGT-1",
        summary="Invoice Import",
        start=date(2026, 1, 1),
        target=date(2026, 3, 1),
        progress="done",
        team="Team A",
    )
    second = _seed_root(
        db,
        key="PMGT-2",
        summary="Invoice Import Polish",
        start=date(2025, 12, 1),
        target=date(2026, 6, 1),
        progress="planned",
        team="Team B",
    )
    standalone = _seed_root(
        db,
        key="PMGT-3",
        summary="Standalone Reporting",
        start=date(2026, 2, 1),
        target=date(2026, 7, 1),
        progress="in progress",
        team="Team C",
    )
    family = JiraFeatureFamily(name="Invoice Import", active=True)
    db.add(family)
    db.flush()
    db.add_all(
        [
            JiraFeatureFamilyMember(family_id=family.id, feature_root_id=first.id),
            JiraFeatureFamilyMember(family_id=family.id, feature_root_id=second.id),
        ]
    )
    _add_hours(db, first, hours=Decimal("2.5"), team="Team A")
    _add_hours(db, second, hours=Decimal("3.5"), team="Team B")
    _add_hours(db, standalone, hours=Decimal("4.0"), team="Team C")
    db.commit()

    matrix = build_feature_family_hours_matrix(
        db,
        settings_json={},
        months=1,
        anchor=date(2026, 5, 28),
    )

    assert len(matrix.rows) == 2
    row = next(row for row in matrix.rows if row.label == "Invoice Import")
    assert row.label == "Invoice Import"
    assert row.feature_count == 2
    assert row.start_date == "2025-12-01"
    assert row.target_end_date == "2026-06-01"
    assert row.delivery_progress == "in progress"
    assert row.team_names == ["Team A", "Team B"]
    assert row.hours_by_period["2026-05"] == 6.0
    assert row.total_hours == 6.0
    standalone_row = next(row for row in matrix.rows if row.label == "Standalone Reporting")
    assert standalone_row.family_id == -standalone.id
    assert standalone_row.feature_count == 1
    assert standalone_row.team_names == ["Team C"]
    assert standalone_row.hours_by_period["2026-05"] == 4.0


def test_feature_family_matrix_normalizes_team_names() -> None:
    db = _session()
    first = _seed_root(
        db,
        key="PMGT-10",
        summary="World Feature",
        start=date(2026, 1, 1),
        target=date(2026, 3, 1),
        progress="done",
        team="World",
    )
    second = _seed_root(
        db,
        key="PMGT-11",
        summary="Tantrum Feature",
        start=date(2026, 1, 1),
        target=date(2026, 3, 1),
        progress="done",
        team="Team Tantrum",
    )
    family = JiraFeatureFamily(name="Mixed Teams", active=True)
    db.add(family)
    db.flush()
    db.add_all(
        [
            JiraFeatureFamilyMember(family_id=family.id, feature_root_id=first.id),
            JiraFeatureFamilyMember(family_id=family.id, feature_root_id=second.id),
        ]
    )
    _add_hours(db, first, hours=Decimal("2.0"), team="Team World")
    _add_hours(db, second, hours=Decimal("3.0"), team="Tantrum")
    db.commit()

    matrix = build_feature_family_hours_matrix(
        db,
        settings_json={},
        months=1,
        anchor=date(2026, 5, 28),
    )

    row = next(row for row in matrix.rows if row.label == "Mixed Teams")
    assert row.team_names == ["Team Tantrum", "Team World"]
    assert matrix.available_teams == ["Team Tantrum", "Team World"]

    filtered = build_feature_family_hours_matrix(
        db,
        settings_json={},
        months=1,
        anchor=date(2026, 5, 28),
        team_filter="Team World",
    )
    filtered_row = next(row for row in filtered.rows if row.label == "Mixed Teams")
    assert filtered_row.total_hours == 2.0

