from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.jira_analytics.models import (
    JiraIssue,
    JiraProject,
    JiraUser,
    JiraUserMonthlyHrworksHours,
    JiraUserRoleAssignment,
    MonthlyAllocatedEffort,
    MonthlyTopicEffortBase,
)
from app.jira_analytics.reports.reports_service import (
    availability_vs_booked,
    work_allocation_heatmap,
)
from app.models.base import Base
from app.services.jira_user_assignments import get_assignment_for_allocated_source


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True)
    return factory()


def test_heatmap_topic_sort_order_within_team() -> None:
    with _session() as db:
        db.add(
            JiraUserRoleAssignment(
                user_account_id="dev-1",
                user_email="dev@example.com",
                display_name="Dev",
                role_name="Developer",
                team_name="Sort Team",
                valid_from=date(2020, 1, 1),
            )
        )
        common = dict(
            period_month=date(2026, 3, 1),
            source_user_email="dev-1",
            source_display_name="Dev",
            source_role_name="Developer",
            allocation_kind="direct_worklog",
            rule_snapshot_json={},
        )
        db.add_all(
            [
                MonthlyAllocatedEffort(
                    **common,
                    topic_type="feature",
                    feature_key="PMGT-100",
                    feature_name="Idea",
                    hours=Decimal("1"),
                ),
                MonthlyAllocatedEffort(
                    **common,
                    topic_type="tech_support",
                    hours=Decimal("2"),
                ),
                MonthlyAllocatedEffort(
                    **{
                        **common,
                        "allocation_kind": "indirect_allocated",
                    },
                    topic_type="tech_support",
                    hours=Decimal("6"),
                ),
                MonthlyAllocatedEffort(
                    **common,
                    topic_type="unassigned_bug",
                    hours=Decimal("3"),
                ),
                MonthlyAllocatedEffort(
                    **common,
                    topic_type="issue_without_feature",
                    issue_key="BM-1",
                    hours=Decimal("4"),
                ),
                MonthlyAllocatedEffort(
                    **common,
                    topic_type="feature",
                    feature_key="BM-200",
                    feature_name="Other",
                    hours=Decimal("5"),
                ),
            ]
        )
        db.commit()

        report = work_allocation_heatmap(
            db,
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
            team=None,
        )

    topics = [topic["topic"] for topic in report.series[0]["topics"]]
    assert topics == [
        "Issue Without Feature",
        "Unassigned Bugs",
        "Tech Support",
        "PMGT-100 — Idea",
        "BM-200 — Other",
    ]
    tech_support = next(
        topic for topic in report.series[0]["topics"] if topic["topic"] == "Tech Support"
    )
    assert tech_support["total_hours"] == 8.0


def test_work_allocation_heatmap_groups_by_assignment_team_topic_and_person() -> None:
    with _session() as db:
        db.add_all(
            [
                JiraUserRoleAssignment(
                    user_account_id="dev-alpha",
                    user_email="alpha@example.com",
                    display_name="Alpha Dev",
                    role_name="Developer",
                    team_name="Alpha Team",
                    valid_from=date(2020, 1, 1),
                ),
                JiraUserRoleAssignment(
                    user_account_id="qa-beta",
                    user_email="beta@example.com",
                    display_name="Beta QA",
                    role_name="QA",
                    team_name="Beta Team",
                    valid_from=date(2020, 1, 1),
                ),
                JiraUserRoleAssignment(
                    user_account_id="po-gamma",
                    user_email="gamma@example.com",
                    display_name="Gamma PO",
                    role_name="Product Owner",
                    team_name="Gamma Team",
                    valid_from=date(2020, 1, 1),
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 3, 1),
                    topic_type="feature",
                    feature_key="FEAT-1",
                    feature_name="Checkout",
                    source_user_email="dev-alpha",
                    source_display_name="Alpha Dev",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=Decimal("8"),
                    rule_snapshot_json={},
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 3, 1),
                    topic_type="feature",
                    feature_key="FEAT-1",
                    feature_name="Checkout",
                    source_user_email="qa-beta",
                    source_display_name="Beta QA",
                    source_role_name="QA",
                    allocation_kind="direct_worklog",
                    hours=Decimal("2"),
                    rule_snapshot_json={},
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 3, 1),
                    topic_type="shared_overhead",
                    source_user_email="po-gamma",
                    source_display_name="Gamma PO",
                    source_role_name="Product Owner",
                    allocation_kind="shared_overhead",
                    hours=Decimal("40"),
                    rule_snapshot_json={},
                ),
            ]
        )
        db.commit()

        report = work_allocation_heatmap(
            db,
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
            team=None,
        )

    assert report.filters["roles"] == ["Developer", "QA"]
    assert report.filters["available_teams"] == ["Alpha Team", "Beta Team"]
    assert len(report.series) == 2
    alpha = next(item for item in report.series if item["team"] == "Alpha Team")
    assert alpha["topics"][0]["topic"] == "FEAT-1 — Checkout"
    assert alpha["topics"][0]["people"] == [
        {"person": "Alpha Dev", "hours": 8.0, "dev_hours": 8.0, "qa_hours": 0.0}
    ]
    assert alpha["topics"][0]["dev_hours"] == 8.0
    assert alpha["topics"][0]["qa_hours"] == 0.0
    assert alpha["dev_hours"] == 8.0
    assert alpha["qa_hours"] == 0.0
    assert report.table == [
        {
            "team": "Alpha Team",
            "topic": "FEAT-1 — Checkout",
            "person": "Alpha Dev",
            "hours": 8.0,
            "dev_hours": 8.0,
            "qa_hours": 0.0,
        },
        {
            "team": "Beta Team",
            "topic": "FEAT-1 — Checkout",
            "person": "Beta QA",
            "hours": 2.0,
            "dev_hours": 0.0,
            "qa_hours": 2.0,
        },
    ]


def test_availability_vs_booked_groups_monthly_capacity_by_team_and_person() -> None:
    with _session() as db:
        user = JiraUser(
            account_id="dev-alpha",
            display_name="Alpha Dev",
            email_address="alpha@example.com",
        )
        qa = JiraUser(
            account_id="qa-beta",
            display_name="Beta QA",
            email_address="beta@example.com",
        )
        po = JiraUser(
            account_id="po-gamma",
            display_name="Gamma PO",
            email_address="gamma@example.com",
        )
        db.add_all([user, qa, po])
        db.flush()
        project = JiraProject(jira_project_id="100", key="BM", name="Business Manager")
        db.add(project)
        db.flush()
        issue = JiraIssue(
            jira_issue_id="200",
            key="BM-1",
            project_id=project.id,
            issue_type_name="Task",
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(issue)
        db.flush()
        db.add_all(
            [
                JiraUserRoleAssignment(
                    jira_user_id=user.id,
                    user_account_id=user.account_id,
                    user_email=user.email_address,
                    display_name=user.display_name,
                    role_name="Developer",
                    team_name="Alpha Team",
                    valid_from=date(2020, 1, 1),
                ),
                JiraUserRoleAssignment(
                    jira_user_id=qa.id,
                    user_account_id=qa.account_id,
                    user_email=qa.email_address,
                    display_name=qa.display_name,
                    role_name="QA",
                    team_name="Alpha Team",
                    valid_from=date(2020, 1, 1),
                ),
                JiraUserRoleAssignment(
                    jira_user_id=po.id,
                    user_account_id=po.account_id,
                    user_email=po.email_address,
                    display_name=po.display_name,
                    role_name="Product Owner",
                    team_name="Alpha Team",
                    valid_from=date(2020, 1, 1),
                ),
                JiraUserMonthlyHrworksHours(
                    jira_user_id=user.id,
                    month_start=date(2026, 3, 1),
                    month_end=date(2026, 3, 31),
                    planned_working_hours=Decimal("160"),
                    clocked_working_hours=Decimal("150"),
                ),
                JiraUserMonthlyHrworksHours(
                    jira_user_id=qa.id,
                    month_start=date(2026, 3, 1),
                    month_end=date(2026, 3, 31),
                    planned_working_hours=Decimal("120"),
                    clocked_working_hours=Decimal("118"),
                ),
                JiraUserMonthlyHrworksHours(
                    jira_user_id=po.id,
                    month_start=date(2026, 3, 1),
                    month_end=date(2026, 3, 31),
                    planned_working_hours=Decimal("100"),
                    clocked_working_hours=Decimal("95"),
                ),
                MonthlyTopicEffortBase(
                    period_month=date(2026, 3, 1),
                    issue_id=issue.id,
                    issue_key=issue.key,
                    user_account_id=user.account_id,
                    display_name=user.display_name,
                    role_name="Developer",
                    topic_type="feature",
                    direct_hours=Decimal("80"),
                ),
                MonthlyTopicEffortBase(
                    period_month=date(2026, 3, 1),
                    issue_id=issue.id,
                    issue_key=issue.key,
                    user_account_id=qa.account_id,
                    display_name=qa.display_name,
                    role_name="QA",
                    topic_type="feature",
                    direct_hours=Decimal("60"),
                ),
                MonthlyTopicEffortBase(
                    period_month=date(2026, 3, 1),
                    issue_id=issue.id,
                    issue_key=issue.key,
                    user_account_id=po.account_id,
                    display_name=po.display_name,
                    role_name="Product Owner",
                    topic_type="feature",
                    direct_hours=Decimal("40"),
                ),
            ]
        )
        db.commit()

        report = availability_vs_booked(
            db,
            date_from=date(2026, 3, 1),
            date_to=date(2026, 3, 31),
            team=None,
        )

    assert report.summary["available_hours"] == 280.0
    assert report.summary["logged_hours"] == 140.0
    assert report.summary["utilization_ratio"] == 0.5
    assert report.filters["available_teams"] == [
        "Team Tantrum",
        "Team World",
        "Cosmic Coders",
        "FreeDevs",
    ]
    assert report.filters["chart_teams"] == ["Alpha Team"]
    assert report.table == [
        {
            "month": "2026-03-01",
            "team": "Alpha Team",
            "person": "Beta QA",
            "role": "QA",
            "available_hours": 120.0,
            "clocked_hours": 118.0,
            "logged_hours": 60.0,
            "remaining_hours": 60.0,
            "utilization_ratio": 0.5,
        },
        {
            "month": "2026-03-01",
            "team": "Alpha Team",
            "person": "Alpha Dev",
            "role": "Developer",
            "available_hours": 160.0,
            "clocked_hours": 150.0,
            "logged_hours": 80.0,
            "remaining_hours": 80.0,
            "utilization_ratio": 0.5,
        },
    ]
    assert report.series == [
        {
            "period": "2026-03-01",
            "teams": [
                {
                    "team": "Alpha Team",
                    "month": "2026-03-01",
                    "available_hours": 280.0,
                    "clocked_hours": 268.0,
                    "logged_hours": 140.0,
                    "remaining_hours": 140.0,
                    "utilization_ratio": 0.5,
                    "people": [
                        report.table[1],
                        report.table[0],
                    ],
                }
            ],
            "Alpha Team__logged_hours": 140.0,
            "Alpha Team__remaining_hours": 140.0,
            "Alpha Team__available_hours": 280.0,
            "Alpha Team__utilization_ratio": 0.5,
        }
    ]


def test_availability_vs_booked_excludes_teams_without_hrworks_capacity() -> None:
    with _session() as db:
        user = JiraUser(
            account_id="dev-missing-hr",
            display_name="Missing HR Dev",
            email_address="missing@example.com",
        )
        db.add(user)
        db.flush()
        project = JiraProject(jira_project_id="missing-100", key="BM", name="Business Manager")
        db.add(project)
        db.flush()
        issue = JiraIssue(
            jira_issue_id="missing-200",
            key="BM-2",
            project_id=project.id,
            issue_type_name="Task",
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(issue)
        db.flush()
        db.add_all(
            [
                JiraUserRoleAssignment(
                    jira_user_id=user.id,
                    user_account_id=user.account_id,
                    user_email=user.email_address,
                    display_name=user.display_name,
                    role_name="Developer",
                    team_name="Alpha Team",
                    valid_from=date(2020, 1, 1),
                ),
                MonthlyTopicEffortBase(
                    period_month=date(2026, 4, 1),
                    issue_id=issue.id,
                    issue_key=issue.key,
                    user_account_id=user.account_id,
                    display_name=user.display_name,
                    role_name="Developer",
                    topic_type="feature",
                    direct_hours=Decimal("8"),
                ),
            ]
        )
        db.commit()

        report = availability_vs_booked(
            db,
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 30),
            team="Alpha Team",
        )

    assert report.summary["available_hours"] == 0.0
    assert report.summary["logged_hours"] == 0.0
    assert report.summary["utilization_ratio"] is None
    assert report.summary["missing_hrworks_people"] == 0
    assert report.filters["available_teams"] == [
        "Team Tantrum",
        "Team World",
        "Cosmic Coders",
        "FreeDevs",
    ]
    assert report.filters["chart_teams"] == []
    assert report.table == []
    assert report.series == []


def test_availability_vs_booked_keeps_all_teams_in_filter_when_team_selected() -> None:
    with _session() as db:
        alpha_dev = JiraUser(
            account_id="alpha-dev",
            display_name="Alpha Dev",
            email_address="alpha@example.com",
        )
        beta_dev = JiraUser(
            account_id="beta-dev",
            display_name="Beta Dev",
            email_address="beta@example.com",
        )
        db.add_all([alpha_dev, beta_dev])
        db.flush()
        db.add_all(
            [
                JiraUserRoleAssignment(
                    jira_user_id=alpha_dev.id,
                    user_account_id=alpha_dev.account_id,
                    user_email=alpha_dev.email_address,
                    display_name=alpha_dev.display_name,
                    role_name="Developer",
                    team_name="Alpha Team",
                    valid_from=date(2020, 1, 1),
                ),
                JiraUserRoleAssignment(
                    jira_user_id=beta_dev.id,
                    user_account_id=beta_dev.account_id,
                    user_email=beta_dev.email_address,
                    display_name=beta_dev.display_name,
                    role_name="Developer",
                    team_name="Beta Team",
                    valid_from=date(2020, 1, 1),
                ),
                JiraUserMonthlyHrworksHours(
                    jira_user_id=alpha_dev.id,
                    month_start=date(2026, 3, 1),
                    month_end=date(2026, 3, 31),
                    planned_working_hours=Decimal("160"),
                    clocked_working_hours=Decimal("150"),
                ),
                JiraUserMonthlyHrworksHours(
                    jira_user_id=beta_dev.id,
                    month_start=date(2026, 3, 1),
                    month_end=date(2026, 3, 31),
                    planned_working_hours=Decimal("140"),
                    clocked_working_hours=Decimal("130"),
                ),
            ]
        )
        db.commit()

        report = availability_vs_booked(
            db,
            date_from=date(2026, 3, 1),
            date_to=date(2026, 3, 31),
            team="Alpha Team",
        )

    assert report.filters["available_teams"] == [
        "Team Tantrum",
        "Team World",
        "Cosmic Coders",
        "FreeDevs",
    ]
    assert report.filters["chart_teams"] == ["Alpha Team"]
    assert len(report.table) == 1
    assert report.table[0]["team"] == "Alpha Team"


def test_get_assignment_for_allocated_source_uses_current_team_for_historical_months() -> None:
    with _session() as db:
        user = JiraUser(
            account_id="712020:historical",
            display_name="Historical Dev",
            email_address="historical@plunet.com",
        )
        db.add(user)
        db.flush()
        db.add(
            JiraUserRoleAssignment(
                jira_user_id=user.id,
                user_account_id=user.account_id,
                user_email=user.email_address,
                display_name=user.display_name,
                role_name="Developer",
                team_name="Rocket Rangers",
                valid_from=date(2026, 5, 26),
            )
        )
        db.commit()

        row = get_assignment_for_allocated_source(
            db,
            source_user_email=user.account_id,
            display_name=user.display_name,
            as_of=date(2024, 1, 1),
        )

    assert row is not None
    assert row.team_name == "Rocket Rangers"


def test_get_assignment_for_allocated_source_resolves_by_jira_user_id() -> None:
    with _session() as db:
        user = JiraUser(
            account_id="jira-acc-99",
            display_name="Real Name",
            email_address="real.name@plunet.com",
        )
        db.add(user)
        db.flush()
        db.add(
            JiraUserRoleAssignment(
                jira_user_id=user.id,
                user_account_id=user.account_id,
                user_email=user.email_address,
                display_name=user.display_name,
                role_name="Developer",
                team_name="Cosmic Coders",
                valid_from=date(2020, 1, 1),
            )
        )
        db.commit()

        row = get_assignment_for_allocated_source(
            db,
            source_user_email="real.name@plunet.com",
            display_name="Real Name",
            as_of=date(2026, 3, 1),
        )

    assert row is not None
    assert row.team_name == "Cosmic Coders"


def test_work_allocation_heatmap_uses_assignment_team_when_source_is_email() -> None:
    with _session() as db:
        user = JiraUser(
            account_id="557058:abc123",
            display_name="Jane Dev",
            email_address="jane@plunet.com",
        )
        db.add(user)
        db.flush()
        db.add(
            JiraUserRoleAssignment(
                jira_user_id=user.id,
                user_account_id=user.account_id,
                user_email=user.email_address,
                display_name=user.display_name,
                role_name="Developer",
                team_name="Rocket Rangers",
                valid_from=date(2020, 1, 1),
            )
        )
        db.add(
            MonthlyAllocatedEffort(
                period_month=date(2026, 3, 1),
                topic_type="feature",
                feature_key="FEAT-9",
                source_user_email="jane@plunet.com",
                source_display_name="Jane Dev",
                source_role_name="Developer",
                allocation_kind="indirect_allocated",
                hours=Decimal("4"),
                rule_snapshot_json={},
            )
        )
        db.commit()

        report = work_allocation_heatmap(
            db,
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
            team=None,
        )

    assert report.series[0]["team"] == "Rocket Rangers"


def test_work_allocation_heatmap_filters_by_team_param() -> None:
    with _session() as db:
        db.add_all(
            [
                JiraUserRoleAssignment(
                    user_account_id="dev-alpha",
                    user_email="alpha@example.com",
                    display_name="Alpha Dev",
                    role_name="Developer",
                    team_name="Alpha Team",
                    valid_from=date(2020, 1, 1),
                ),
                JiraUserRoleAssignment(
                    user_account_id="qa-beta",
                    user_email="beta@example.com",
                    display_name="Beta QA",
                    role_name="QA",
                    team_name="Beta Team",
                    valid_from=date(2020, 1, 1),
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 3, 1),
                    topic_type="tech_support",
                    source_user_email="dev-alpha",
                    source_display_name="Alpha Dev",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=Decimal("5"),
                    rule_snapshot_json={},
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 3, 1),
                    topic_type="tech_support",
                    source_user_email="qa-beta",
                    source_display_name="Beta QA",
                    source_role_name="QA",
                    allocation_kind="direct_worklog",
                    hours=Decimal("3"),
                    rule_snapshot_json={},
                ),
            ]
        )
        db.commit()

        report = work_allocation_heatmap(
            db,
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
            team="Alpha Team",
        )

    assert len(report.series) == 1
    assert report.series[0]["team"] == "Alpha Team"
    assert report.table[0]["person"] == "Alpha Dev"
