from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.jira_analytics.allocation.allocation_service import rebuild_monthly_allocation
from app.jira_analytics.allocation.topic_classifier import classify_topic_type
from app.models.base import Base
from app.jira_analytics.models import (
    AllocationRoleRule,
    JiraFeatureMembership,
    JiraFeatureRoot,
    JiraIssue,
    JiraIssueDetail,
    JiraUser,
    JiraUserMonthlyHrworksHours,
    JiraUserRoleAssignment,
    JiraWorklog,
    MonthlyAllocatedEffort,
    MonthlyTopicEffortBase,
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


def test_classify_topic_type() -> None:
    assert classify_topic_type(feature_root_id=1, issue_type_name="Bug") == "feature"
    assert classify_topic_type(feature_root_id=None, issue_type_name="TechSupport") == "tech_support"
    assert classify_topic_type(feature_root_id=None, issue_type_name="Bug") == "unassigned_bug"


def test_allocation_direct_and_overhead(db: Session) -> None:
    user = JiraUser(account_id="acc-dev", display_name="Dev User", email_address="dev@test.com")
    db.add(user)
    db.flush()
    issue = JiraIssue(
        jira_issue_id="1",
        key="BM-1",
        issue_type_name="Story",
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(issue)
    db.flush()
    db.add(JiraIssueDetail(issue_id=issue.id, team_name="Alpha"))
    root = JiraFeatureRoot(
        root_issue_id=issue.id,
        root_key="PMGT-1",
        root_project_key="PMGT",
        detection_rule="test",
    )
    db.add(root)
    db.flush()
    db.add(
        JiraFeatureMembership(
            feature_root_id=root.id,
            member_issue_id=issue.id,
            depth=0,
            path_issue_keys=["PMGT-1"],
            inclusion_reason="root",
        )
    )
    period = date(2026, 5, 1)
    db.add(
        JiraWorklog(
            issue_id=issue.id,
            jira_worklog_id="wl1",
            author_user_id=user.id,
            author_account_id=user.account_id,
            author_display_name=user.display_name,
            started_at=datetime(2026, 5, 10, 10, 0, tzinfo=timezone.utc),
            time_spent_seconds=3600,
        )
    )
    for role_name, direct, indirect, overhead, scope in [
        ("Developer", True, False, 0, "direct_issue"),
        ("Product Manager", False, True, 30, "global"),
    ]:
        db.add(
            AllocationRoleRule(
                role_name=role_name,
                is_direct_production_role=direct,
                is_indirect_role=indirect,
                overhead_percentage=Decimal(overhead),
                allocation_scope=scope,
                allocation_base="direct_production_hours",
            )
        )
    db.add(
        JiraUserRoleAssignment(
            jira_user_id=user.id,
            user_account_id=user.account_id,
            user_email=user.email_address or "dev@test.com",
            display_name=user.display_name or "Dev",
            role_name="Developer",
            team_name="Alpha",
            valid_from=date(2020, 1, 1),
        )
    )
    pm_user = JiraUser(account_id="acc-pm", display_name="PM User", email_address="pm@test.com")
    db.add(pm_user)
    db.flush()
    db.add(
        JiraUserRoleAssignment(
            jira_user_id=pm_user.id,
            user_account_id=pm_user.account_id,
            user_email=pm_user.email_address or "pm@test.com",
            display_name=pm_user.display_name or "PM",
            role_name="Product Manager",
            team_name="Alpha",
            valid_from=date(2020, 1, 1),
        )
    )
    db.add(
        JiraUserMonthlyHrworksHours(
            jira_user_id=pm_user.id,
            month_start=period,
            month_end=date(2026, 5, 31),
            planned_working_hours=Decimal("160"),
            clocked_working_hours=Decimal("100"),
        )
    )
    db.commit()

    result = rebuild_monthly_allocation(db, period_months=[period])
    assert result["allocation_rows"] > 0
    direct = db.query(MonthlyAllocatedEffort).filter_by(allocation_kind="direct_worklog").all()
    assert len(direct) >= 1
    overhead = db.query(MonthlyAllocatedEffort).filter_by(allocation_kind="shared_overhead").all()
    assert len(overhead) >= 1
    topic = db.query(MonthlyTopicEffortBase).all()
    assert len(topic) >= 1


def test_allocation_uses_first_assignment_for_existing_worklogs(db: Session) -> None:
    user = JiraUser(account_id="acc-dev", display_name="Dev User", email_address="dev@test.com")
    db.add(user)
    db.flush()
    issue = JiraIssue(
        jira_issue_id="2",
        key="BM-2",
        issue_type_name="Story",
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(issue)
    db.flush()
    db.add(JiraIssueDetail(issue_id=issue.id, team_name="Alpha"))
    period = date(2026, 5, 1)
    db.add(
        JiraWorklog(
            issue_id=issue.id,
            jira_worklog_id="wl-before-assignment",
            author_user_id=user.id,
            author_account_id=user.account_id,
            author_display_name=user.display_name,
            started_at=datetime(2026, 5, 10, 10, 0, tzinfo=timezone.utc),
            time_spent_seconds=3600,
        )
    )
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
            user_email=user.email_address or "dev@test.com",
            display_name=user.display_name or "Dev",
            role_name="Developer",
            team_name="Alpha",
            valid_from=date(2026, 5, 26),
        )
    )
    db.commit()

    result = rebuild_monthly_allocation(db, period_months=[period])

    assert result["topic_rows"] == 1
    direct = db.query(MonthlyAllocatedEffort).filter_by(allocation_kind="direct_worklog").one()
    assert direct.source_role_name == "Developer"
