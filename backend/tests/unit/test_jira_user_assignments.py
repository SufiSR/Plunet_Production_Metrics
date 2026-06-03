from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.jira_analytics.allocation.allocation_service import rebuild_monthly_allocation
from app.jira_analytics.models import (
    AllocationRoleRule,
    JiraIssue,
    JiraIssueDetail,
    JiraProject,
    JiraUser,
    JiraUserMonthlyHrworksHours,
    JiraUserRoleAssignment,
    JiraWorklog,
    MonthlyAllocatedEffort,
)
from app.models.base import Base
from app.services.jira_user_assignments import (
    get_current_assignment_row,
    is_reporting_excluded,
    list_worklog_assignments,
    load_allocation_role_rules,
    upsert_role_assignment,
)


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


def _seed_rules(db: Session) -> dict[str, AllocationRoleRule]:
    rules = [
        AllocationRoleRule(
            role_name="Developer",
            is_direct_production_role=True,
            is_indirect_role=False,
            overhead_percentage=Decimal(0),
            allocation_scope="direct_issue",
            allocation_base="direct_production_hours",
        ),
        AllocationRoleRule(
            role_name="Product Owner",
            is_direct_production_role=False,
            is_indirect_role=True,
            overhead_percentage=Decimal(20),
            allocation_scope="team_only",
            allocation_base="direct_production_hours",
        ),
        AllocationRoleRule(
            role_name="System Architect",
            is_direct_production_role=False,
            is_indirect_role=True,
            overhead_percentage=Decimal(30),
            allocation_scope="global",
            allocation_base="direct_production_hours",
        ),
        AllocationRoleRule(
            role_name="Solutions Engineer",
            is_direct_production_role=True,
            is_indirect_role=False,
            overhead_percentage=Decimal(0),
            allocation_scope="direct_issue",
            allocation_base="direct_production_hours",
        ),
    ]
    for r in rules:
        db.add(r)
    db.commit()
    return {r.role_name: r for r in rules}


def test_reporting_excluded_skips_indirect_allocation(db: Session) -> None:
    _seed_rules(db)
    period = date(2026, 5, 1)
    project = JiraProject(jira_project_id="p1", key="BM", name="BM")
    db.add(project)
    db.flush()
    dev = JiraUser(account_id="dev-1", display_name="Dev", email_address="dev@test.com")
    arch = JiraUser(
        account_id="arch-1",
        display_name="Arch",
        email_address="arch@test.com",
        reporting_excluded=True,
    )
    db.add_all([dev, arch])
    db.flush()
    issue = JiraIssue(
        jira_issue_id="1",
        key="BM-1",
        project_id=project.id,
        issue_type_name="Story",
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(issue)
    db.flush()
    db.add(JiraIssueDetail(issue_id=issue.id, team_name="World"))
    db.add(
        JiraWorklog(
            issue_id=issue.id,
            jira_worklog_id="wl1",
            author_user_id=dev.id,
            author_account_id=dev.account_id,
            started_at=datetime(2026, 5, 10, 10, 0, tzinfo=timezone.utc),
            time_spent_seconds=3600,
        )
    )
    for user, role in ((dev, "Developer"), (arch, "System Architect")):
        db.add(
            JiraUserRoleAssignment(
                jira_user_id=user.id,
                user_account_id=user.account_id,
                user_email=user.email_address or "",
                display_name=user.display_name or "",
                role_name=role,
                team_name="World",
                valid_from=date(2020, 1, 1),
            )
        )
    db.add(
        JiraUserMonthlyHrworksHours(
            jira_user_id=arch.id,
            month_start=period,
            month_end=date(2026, 5, 31),
            planned_working_hours=Decimal("160"),
            clocked_working_hours=Decimal("100"),
        )
    )
    db.commit()
    assert is_reporting_excluded(db, account_id=arch.account_id) is True
    rebuild_monthly_allocation(db, period_months=[period])
    indirect = (
        db.query(MonthlyAllocatedEffort)
        .filter_by(allocation_kind="indirect_allocated", source_user_email=arch.email_address)
        .all()
    )
    assert indirect == []


def test_po_team_only_project_proportional(db: Session) -> None:
    _seed_rules(db)
    period = date(2026, 5, 1)
    p_world = JiraProject(jira_project_id="pw", key="WLD", name="World")
    p_other = JiraProject(jira_project_id="po", key="OTH", name="Other")
    db.add_all([p_world, p_other])
    db.flush()
    dev = JiraUser(account_id="dev-1", display_name="Dev", email_address="dev@test.com")
    po = JiraUser(account_id="po-1", display_name="PO", email_address="po@test.com")
    db.add_all([dev, po])
    db.flush()
    issue_world = JiraIssue(
        jira_issue_id="w1",
        key="WLD-1",
        project_id=p_world.id,
        issue_type_name="Story",
        last_seen_at=datetime.now(timezone.utc),
    )
    issue_other_team = JiraIssue(
        jira_issue_id="o1",
        key="OTH-1",
        project_id=p_other.id,
        issue_type_name="Story",
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add_all([issue_world, issue_other_team])
    db.flush()
    db.add(JiraIssueDetail(issue_id=issue_world.id, team_name="World"))
    db.add(JiraIssueDetail(issue_id=issue_other_team.id, team_name="Other"))
    db.add_all(
        [
            JiraWorklog(
                issue_id=issue_world.id,
                jira_worklog_id="wl1",
                author_account_id=dev.account_id,
                started_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
                time_spent_seconds=7200,
            ),
            JiraWorklog(
                issue_id=issue_other_team.id,
                jira_worklog_id="wl2",
                author_account_id=dev.account_id,
                started_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
                time_spent_seconds=3600,
            ),
        ]
    )
    db.add(
        JiraUserRoleAssignment(
            jira_user_id=dev.id,
            user_account_id=dev.account_id,
            user_email=dev.email_address or "",
            display_name=dev.display_name or "",
            role_name="Developer",
            team_name="World",
            valid_from=date(2020, 1, 1),
        )
    )
    db.add(
        JiraUserRoleAssignment(
            jira_user_id=po.id,
            user_account_id=po.account_id,
            user_email=po.email_address or "",
            display_name=po.display_name or "",
            role_name="Product Owner",
            team_name="World",
            allocatable_percentage=Decimal("80"),
            allocation_scope="team_only",
            valid_from=date(2020, 1, 1),
        )
    )
    db.add(
        JiraUserMonthlyHrworksHours(
            jira_user_id=po.id,
            month_start=period,
            month_end=date(2026, 5, 31),
            planned_working_hours=Decimal("100"),
            clocked_working_hours=Decimal("100"),
        )
    )
    db.commit()
    rebuild_monthly_allocation(db, period_months=[period])
    po_rows = (
        db.query(MonthlyAllocatedEffort)
        .filter_by(allocation_kind="indirect_allocated")
        .filter(MonthlyAllocatedEffort.source_user_email == po.email_address)
        .all()
    )
    assert len(po_rows) >= 1
    keys = {r.issue_key for r in po_rows}
    assert "WLD-1" in keys
    assert "OTH-1" not in keys


def test_list_worklog_assignments_from_db(db: Session) -> None:
    _seed_rules(db)
    user = JiraUser(account_id="acc-1", display_name="Dev One", email_address="d@test.com")
    db.add(user)
    db.flush()
    rules = load_allocation_role_rules(db)
    upsert_role_assignment(
        db,
        user=user,
        role_name="Developer",
        team_name="Alpha",
        allocatable_percentage=None,
        allocation_scope=None,
        rules=rules,
    )
    db.commit()
    items = list_worklog_assignments(db)
    assert len(items) == 1
    assert items[0].jira_account_id == "acc-1"
    assert items[0].role == "dev"


def test_solutions_engineer_assignment_uses_worklog_hours_bucket(db: Session) -> None:
    _seed_rules(db)
    user = JiraUser(account_id="acc-se", display_name="SE One", email_address="se@test.com")
    db.add(user)
    db.flush()
    rules = load_allocation_role_rules(db)
    upsert_role_assignment(
        db,
        user=user,
        role_name="Solutions Engineer",
        team_name="Customer",
        allocatable_percentage=None,
        allocation_scope=None,
        rules=rules,
    )
    db.commit()

    items = list_worklog_assignments(db)

    assert len(items) == 1
    assert items[0].jira_account_id == "acc-se"
    assert items[0].role == "sup"
    assert items[0].team == "Customer"


def test_historical_assignment_remains_active_for_old_periods(db: Session) -> None:
    _seed_rules(db)
    user = JiraUser(account_id="acc-history", display_name="User", email_address="u@test.com")
    db.add(user)
    db.flush()
    old = JiraUserRoleAssignment(
        jira_user_id=user.id,
        user_account_id=user.account_id,
        user_email=user.email_address or "",
        display_name=user.display_name or "",
        role_name="Developer",
        team_name="Alpha",
        valid_from=date(2020, 1, 1),
    )
    db.add(old)
    db.commit()

    rules = load_allocation_role_rules(db)
    upsert_role_assignment(
        db,
        user=user,
        role_name="Product Owner",
        team_name="Beta",
        allocatable_percentage=Decimal("80"),
        allocation_scope="team_only",
        rules=rules,
    )
    db.commit()

    historical = get_current_assignment_row(db, jira_user_id=user.id, as_of=date(2020, 2, 1))
    assert historical is not None
    assert historical.role_name == "Developer"
    assert historical.active is True


def test_legacy_author_only_assignment_still_feeds_author_fallback(db: Session) -> None:
    db.add(
        JiraUserRoleAssignment(
            jira_user_id=None,
            user_account_id=None,
            user_email="legacy@test.local",
            display_name="Legacy User",
            role_name="Developer",
            team_name="LegacyTeam",
            valid_from=date(2020, 1, 1),
        )
    )
    db.commit()

    items = list_worklog_assignments(db)

    assert len(items) == 1
    assert items[0].jira_account_id is None
    assert items[0].author == "Legacy User"
    assert items[0].role == "dev"


def test_allocation_skips_direct_worklogs_without_assignment(db: Session) -> None:
    _seed_rules(db)
    period = date(2026, 5, 1)
    project = JiraProject(jira_project_id="p1", key="BM", name="BM")
    db.add(project)
    db.flush()
    user = JiraUser(account_id="unassigned", display_name="Unassigned", email_address="u@test.com")
    db.add(user)
    db.flush()
    issue = JiraIssue(
        jira_issue_id="1",
        key="BM-1",
        project_id=project.id,
        issue_type_name="Story",
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(issue)
    db.flush()
    db.add(JiraIssueDetail(issue_id=issue.id, team_name="Alpha"))
    db.add(
        JiraWorklog(
            issue_id=issue.id,
            jira_worklog_id="wl-unassigned",
            author_user_id=user.id,
            author_account_id=user.account_id,
            author_display_name=user.display_name,
            started_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
            time_spent_seconds=3600,
        )
    )
    db.commit()

    result = rebuild_monthly_allocation(db, period_months=[period])

    assert result["topic_rows"] == 0
    assert db.query(MonthlyAllocatedEffort).count() == 0


def test_solutions_engineer_direct_worklogs_are_allocated(db: Session) -> None:
    _seed_rules(db)
    period = date(2026, 5, 1)
    project = JiraProject(jira_project_id="p-sol", key="SOL", name="Solutions")
    db.add(project)
    db.flush()
    user = JiraUser(account_id="se-1", display_name="Solutions", email_address="se@test.com")
    db.add(user)
    db.flush()
    issue = JiraIssue(
        jira_issue_id="se-1",
        key="SOL-1",
        project_id=project.id,
        issue_type_name="Story",
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(issue)
    db.flush()
    db.add(JiraIssueDetail(issue_id=issue.id, team_name="Customer"))
    db.add(
        JiraUserRoleAssignment(
            jira_user_id=user.id,
            user_account_id=user.account_id,
            user_email=user.email_address or "",
            display_name=user.display_name or "",
            role_name="Solutions Engineer",
            team_name="Customer",
            valid_from=date(2020, 1, 1),
        )
    )
    db.add(
        JiraWorklog(
            issue_id=issue.id,
            jira_worklog_id="wl-se",
            author_user_id=user.id,
            author_account_id=user.account_id,
            author_display_name=user.display_name,
            started_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
            time_spent_seconds=7200,
        )
    )
    db.commit()

    result = rebuild_monthly_allocation(db, period_months=[period])
    rows = db.query(MonthlyAllocatedEffort).filter_by(source_role_name="Solutions Engineer").all()

    assert result["topic_rows"] == 1
    assert len(rows) == 1
    assert rows[0].allocation_kind == "direct_worklog"
    assert rows[0].hours == Decimal("2.0000")
