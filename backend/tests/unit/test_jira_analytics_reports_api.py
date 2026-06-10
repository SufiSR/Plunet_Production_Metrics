from __future__ import annotations

from collections.abc import Generator
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

import app.database as database
from app.api.deps import get_db
from app.jira_analytics.data_quality import WORKLOG_USERS_WITHOUT_ASSIGNMENT_CHECK_ID
from app.jira_analytics.models import (
    JiraFeatureMembership,
    JiraFeatureRoot,
    JiraIssue,
    JiraIssueDetail,
    JiraIssueStatusTransition,
    JiraProject,
    JiraProjectWorkflowMapping,
    JiraUser,
    JiraUserMonthlyHrworksHours,
    JiraUserRoleAssignment,
    JiraWorkflow,
    JiraWorklog,
    MonthlyAllocatedEffort,
    MonthlyTopicEffortBase,
)
from app.jira_analytics.reports.reports_service import _investment_role_bucket, bound_quarter_period
from app.models import Base
from app.models.people_data_user import PeopleDataUser
from app.services.people_data_password_service import hash_password


def test_investment_role_bucket_groups_requested_overhead_roles() -> None:
    for role in ("Product Owner", "Product Manager", "PO", "PM", "Senior Product Manager"):
        assert _investment_role_bucket("indirect_allocated", role) == "product_overhead"
    for role in ("Architect", "System Architect", "Head of Dev", "Head of Development"):
        assert _investment_role_bucket("indirect_allocated", role) == "dev_overhead"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "jira_reports_api.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path.resolve().as_posix()}")
    monkeypatch.setenv("DORA_SESSION_SECRET", "unit-test-session-secret-strings")
    monkeypatch.setenv("DORA_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("DORA_ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("CONFIG_ENCRYPTION_KEY", "devops-429-jira-analytics")
    database._engine = None
    Base.metadata.create_all(database.get_engine())
    maker = sessionmaker(
        bind=database.get_engine(),
        class_=Session,
        autoflush=False,
        autocommit=False,
    )

    def _db() -> Generator[Session, None, None]:
        db = maker()
        try:
            yield db
        finally:
            db.close()

    from app.main import app

    app.dependency_overrides[get_db] = _db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_data_quality_endpoint(client: TestClient) -> None:
    res = client.get("/api/jira-analytics/data-quality")
    assert res.status_code == 200
    assert "data_quality" in res.json()


def _create_people_data_user(
    username: str = "people.viewer",
    password: str = "people-secret-123",
) -> None:
    with Session(database.get_engine()) as db:
        db.add(
            PeopleDataUser(
                username=username,
                username_normalized=username.casefold(),
                password_hash=hash_password(password),
                is_active=True,
            )
        )
        db.commit()


def _login_people_data(client: TestClient) -> None:
    _create_people_data_user()
    response = client.post(
        "/api/auth/people-data/login",
        json={"username": "people.viewer", "password": "people-secret-123"},
    )
    assert response.status_code == 200


def test_people_data_auth_login_logout_and_password_change(client: TestClient) -> None:
    _create_people_data_user()

    login = client.post(
        "/api/auth/people-data/login",
        json={"username": "people.viewer", "password": "people-secret-123"},
    )
    assert login.status_code == 200
    assert login.json()["authenticated"] is True

    changed = client.post(
        "/api/auth/people-data/change-password",
        json={
            "current_password": "people-secret-123",
            "new_password": "people-secret-456",
        },
    )
    assert changed.status_code == 200

    logout = client.post("/api/auth/people-data/logout")
    assert logout.status_code == 204

    old_login = client.post(
        "/api/auth/people-data/login",
        json={"username": "people.viewer", "password": "people-secret-123"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/auth/people-data/login",
        json={"username": "people.viewer", "password": "people-secret-456"},
    )
    assert new_login.status_code == 200


def test_admin_people_data_user_crud(client: TestClient) -> None:
    unauthorized = client.get("/api/admin/people-data-users")
    assert unauthorized.status_code == 401

    client.post("/api/auth/login", json={"username": "admin", "password": "secret"})

    created = client.post(
        "/api/admin/people-data-users",
        json={"username": "analytics.viewer", "password": "people-secret-123"},
    )
    assert created.status_code == 201
    user_id = created.json()["id"]

    listed = client.get("/api/admin/people-data-users")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["username"] == "analytics.viewer"

    patched = client.patch(
        f"/api/admin/people-data-users/{user_id}",
        json={"is_active": False, "password": "people-secret-456"},
    )
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False

    deleted = client.delete(f"/api/admin/people-data-users/{user_id}")
    assert deleted.status_code == 204


def test_data_quality_user_drilldown_ignore_flow(client: TestClient) -> None:
    with Session(database.get_engine()) as db:
        project = JiraProject(jira_project_id="dq-bm", key="BM", name="Business Manager")
        db.add(project)
        db.flush()
        issue = JiraIssue(
            jira_issue_id="dq-1",
            key="BM-DQ-1",
            project_id=project.id,
            issue_type_name="Task",
            last_seen_at=datetime.now(timezone.utc),
        )
        user = JiraUser(
            account_id="dq-user",
            display_name="DQ User",
            email_address="dq.user@example.com",
        )
        db.add_all([issue, user])
        db.flush()
        user_id = user.id
        db.add(
            JiraWorklog(
                issue_id=issue.id,
                jira_worklog_id="dq-wl-1",
                author_user_id=user.id,
                author_account_id=user.account_id,
                author_display_name=user.display_name,
                author_email_address=user.email_address,
                started_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
                time_spent_seconds=7200,
            )
        )
        db.commit()

    path = (
        f"/api/jira-analytics/data-quality/checks/"
        f"{WORKLOG_USERS_WITHOUT_ASSIGNMENT_CHECK_ID}/users"
    )
    initial = client.get(path)
    assert initial.status_code == 200
    assert initial.json()["active_count"] == 1
    assert initial.json()["people_data_restricted"] is True
    assert initial.json()["users"][0]["display_name"] == "Restricted"
    assert initial.json()["users"][0]["total_hours"] == 2.0

    unauthenticated = client.post(f"{path}/{user_id}/ignore", json={"reason": "contractor"})
    assert unauthenticated.status_code == 401

    client.post("/api/auth/login", json={"username": "admin", "password": "secret"})
    ignored = client.post(f"{path}/{user_id}/ignore", json={"reason": "contractor"})
    assert ignored.status_code == 200
    assert ignored.json()["active_count"] == 0
    assert ignored.json()["ignored_count"] == 1
    assert ignored.json()["users"][0]["ignored"] is True

    quality = client.get("/api/jira-analytics/data-quality")
    warning_ids = {w["check_id"] for w in quality.json()["data_quality"]["warnings"]}
    assert WORKLOG_USERS_WITHOUT_ASSIGNMENT_CHECK_ID not in warning_ids

    unignored = client.delete(f"{path}/{user_id}/ignore")
    assert unignored.status_code == 200
    assert unignored.json()["active_count"] == 1
    assert unignored.json()["ignored_count"] == 0


def test_investment_category_endpoint(client: TestClient) -> None:
    res = client.get("/api/jira-analytics/capacity/investment-category")
    assert res.status_code == 200
    assert "series" in res.json()


def test_availability_vs_booked_endpoint(client: TestClient) -> None:
    res = client.get("/api/jira-analytics/teams/availability-vs-booked")
    assert res.status_code == 200
    body = res.json()
    assert "summary" in body
    assert "series" in body
    assert "table" in body


def test_feature_investment_audit_endpoints(client: TestClient) -> None:
    report = client.get("/api/jira-analytics/features/investment-audit")
    assert report.status_code == 200
    assert "table" in report.json()

    issues = client.get("/api/jira-analytics/features/investment-audit/drilldown/issues")
    assert issues.status_code == 200
    assert "table" in issues.json()

    worklogs = client.get(
        "/api/jira-analytics/features/investment-audit/drilldown/worklogs",
        params={"issue_key": "BM-1"},
    )
    assert worklogs.status_code == 200
    assert "table" in worklogs.json()

    export = client.get("/api/jira-analytics/features/investment-audit/export.xlsx")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def test_capacity_forecast_groups_hrworks_capacity_by_assigned_team_and_role(
    client: TestClient,
) -> None:
    with Session(database.get_engine()) as db:
        dev = JiraUser(
            account_id="cap-dev",
            email_address="cap.dev@example.com",
            display_name="Capacity Dev",
        )
        qa = JiraUser(
            account_id="cap-qa",
            email_address="cap.qa@example.com",
            display_name="Capacity QA",
        )
        future_dev = JiraUser(
            account_id="cap-future",
            email_address="cap.future@example.com",
            display_name="Future Dev",
        )
        db.add_all([dev, qa, future_dev])
        db.flush()
        db.add_all(
            [
                JiraUserRoleAssignment(
                    jira_user_id=dev.id,
                    user_account_id=dev.account_id,
                    user_email=dev.email_address,
                    display_name=dev.display_name,
                    role_name="Developer",
                    team_name="Team Tantrum",
                    valid_from=date(2020, 1, 1),
                ),
                JiraUserRoleAssignment(
                    jira_user_id=qa.id,
                    user_account_id=qa.account_id,
                    user_email=qa.email_address,
                    display_name=qa.display_name,
                    role_name="QA",
                    team_name="Team Tantrum",
                    valid_from=date(2020, 1, 1),
                ),
                JiraUserRoleAssignment(
                    jira_user_id=future_dev.id,
                    user_account_id=future_dev.account_id,
                    user_email=future_dev.email_address,
                    display_name=future_dev.display_name,
                    role_name="Developer",
                    team_name="FreeDevs",
                    valid_from=date(2026, 6, 1),
                ),
                JiraUserMonthlyHrworksHours(
                    jira_user_id=dev.id,
                    month_start=date(2026, 5, 1),
                    month_end=date(2026, 5, 31),
                    planned_working_hours=Decimal("144.00"),
                    clocked_working_hours=Decimal("140.00"),
                ),
                JiraUserMonthlyHrworksHours(
                    jira_user_id=qa.id,
                    month_start=date(2026, 5, 1),
                    month_end=date(2026, 5, 31),
                    planned_working_hours=Decimal("80.00"),
                    clocked_working_hours=Decimal("80.00"),
                ),
                JiraUserMonthlyHrworksHours(
                    jira_user_id=dev.id,
                    month_start=date(2026, 6, 1),
                    month_end=date(2026, 6, 30),
                    planned_working_hours=Decimal("160.00"),
                    clocked_working_hours=Decimal("0.00"),
                ),
            ]
        )
        db.commit()

    _login_people_data(client)
    res = client.get(
        "/api/jira-analytics/teams/capacity-forecast",
        params={"from": "2026-05-01", "to": "2026-06-01"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["filters"]["periods"] == ["2026-05-01", "2026-06-01"]
    assert body["filters"]["available_teams"] == [
        "Team Tantrum",
        "Team World",
        "Cosmic Coders",
        "FreeDevs",
    ]
    assert body["filters"]["chart_teams"] == [
        "Team Tantrum",
        "Team World",
        "Cosmic Coders",
    ]
    assert body["summary"]["development_hours"] == 304.0
    assert body["summary"]["qa_hours"] == 80.0
    assert body["series"][0]["Team Tantrum__development_hours"] == 144.0
    assert body["series"][0]["Team Tantrum__qa_hours"] == 80.0
    assert body["series"][1]["Team Tantrum__total_hours"] == 160.0
    rows_by_person = {row["person"]: row for row in body["table"]}
    assert rows_by_person["Capacity Dev"]["role_bucket"] == "Development"
    assert rows_by_person["Capacity Dev"]["hours_by_period"] == {
        "2026-05-01": 144.0,
        "2026-06-01": 160.0,
    }
    assert rows_by_person["Capacity QA"]["role_bucket"] == "QA"
    assert rows_by_person["Future Dev"]["team"] == "FreeDevs"
    assert rows_by_person["Future Dev"]["hours_by_period"]["2026-06-01"] == 0.0


def test_capacity_forecast_includes_freedevs_for_month_when_assignment_valid_on_month_end(
    client: TestClient,
) -> None:
    with Session(database.get_engine()) as db:
        dev = JiraUser(
            account_id="cap-free",
            email_address="cap.free@example.com",
            display_name="Free Capacity Dev",
        )
        db.add(dev)
        db.flush()
        db.add(
            JiraUserRoleAssignment(
                jira_user_id=dev.id,
                user_account_id=dev.account_id,
                user_email=dev.email_address,
                display_name=dev.display_name,
                role_name="Developer",
                team_name="free devs",
                valid_from=date(2026, 5, 15),
            )
        )
        db.add(
            JiraUserMonthlyHrworksHours(
                jira_user_id=dev.id,
                month_start=date(2026, 5, 1),
                month_end=date(2026, 5, 31),
                planned_working_hours=Decimal("120.00"),
                clocked_working_hours=Decimal("0.00"),
            )
        )
        db.commit()

    _login_people_data(client)
    res = client.get(
        "/api/jira-analytics/teams/capacity-forecast",
        params={"from": "2026-05-01", "to": "2026-05-01"},
    )

    assert res.status_code == 200
    body = res.json()
    free_row = next(row for row in body["table"] if row["team"] == "FreeDevs")
    assert free_row["person"] == "Free Capacity Dev"
    assert free_row["hours_by_period"]["2026-05-01"] == 120.0


def test_investment_category_filters_by_monthly_worklog_period_project_and_assignment_team(
    client: TestClient,
) -> None:
    with Session(database.get_engine()) as db:
        bm = JiraProject(jira_project_id="100", key="BM", name="Business Manager")
        crm = JiraProject(jira_project_id="101", key="CRM", name="CRM")
        db.add_all([bm, crm])
        db.flush()
        bm_issue = JiraIssue(
            jira_issue_id="200",
            key="BM-1",
            project_id=bm.id,
            issue_type_name="Task",
            last_seen_at=datetime.now(timezone.utc),
        )
        crm_issue = JiraIssue(
            jira_issue_id="201",
            key="CRM-1",
            project_id=crm.id,
            issue_type_name="Task",
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add_all([bm_issue, crm_issue])
        db.flush()
        db.add(
            JiraUserRoleAssignment(
                user_account_id="acc-alpha",
                user_email="alpha@example.com",
                display_name="Alpha User",
                role_name="Developer",
                team_name="Alpha",
                valid_from=date(2020, 1, 1),
            )
        )
        db.add_all(
            [
                MonthlyAllocatedEffort(
                    period_month=date(2023, 5, 1),
                    topic_type="issue_without_feature",
                    issue_id=bm_issue.id,
                    issue_key=bm_issue.key,
                    source_user_email="acc-alpha",
                    source_display_name="Alpha User",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=Decimal("1.2345"),
                    rule_snapshot_json={},
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2023, 5, 1),
                    topic_type="feature",
                    issue_id=crm_issue.id,
                    issue_key=crm_issue.key,
                    source_user_email="acc-beta",
                    source_display_name="Beta User",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=Decimal("5.00"),
                    rule_snapshot_json={},
                ),
            ]
        )
        db.commit()

    res = client.get(
        "/api/jira-analytics/capacity/investment-category",
        params=[
            ("from", "2023-05-26"),
            ("to", "2023-05-26"),
            ("project_key", "BM"),
            ("project_key", "CRM"),
            ("team", "Alpha"),
        ],
    )

    assert res.status_code == 200
    body = res.json()
    assert body["series"] == [{"period": "2023-05-01", "small_improvements": 1.23}]
    assert body["filters"]["available_teams"] == ["Alpha"]
    assert body["filters"]["available_projects"] == [{"key": "BM", "name": "Business Manager"}]
    assert body["filters"]["project_keys"] == ["BM", "CRM"]


def test_active_vs_passive_filters_main_workflows_and_attributes_team(client: TestClient) -> None:
    with Session(database.get_engine()) as db:
        bm = JiraProject(jira_project_id="avp-bm", key="BM", name="Business Manager")
        pmgt = JiraProject(jira_project_id="avp-pmgt", key="PMGT", name="Product Management")
        db.add_all([bm, pmgt])
        db.flush()
        workflow = JiraWorkflow(
            jira_entity_id="wf-standard",
            name="Standard Plunet Workflow",
            status_order_json=["In Progress", "Ready for code review"],
        )
        other_workflow = JiraWorkflow(
            jira_entity_id="wf-other",
            name="Design Workflow",
            status_order_json=["In Progress"],
        )
        db.add_all([workflow, other_workflow])
        db.flush()
        db.add(
            JiraProjectWorkflowMapping(
                project_id=bm.id,
                issue_type_id="analysis-type",
                issue_type_name="Analysis",
                workflow_id=workflow.id,
            )
        )
        root = JiraIssue(
            jira_issue_id="avp-root",
            key="PMGT-1",
            project_id=pmgt.id,
            issue_type_name="Epic",
            last_seen_at=datetime.now(timezone.utc),
        )
        issue = JiraIssue(
            jira_issue_id="avp-issue",
            key="BM-1",
            project_id=bm.id,
            issue_type_id="analysis-type",
            issue_type_name="Analysis",
            created_at_jira=datetime(2026, 5, 1, tzinfo=timezone.utc),
            resolved_at_jira=datetime(2026, 5, 3, tzinfo=timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        standalone_issue = JiraIssue(
            jira_issue_id="avp-standalone",
            key="BM-2",
            project_id=bm.id,
            issue_type_id="analysis-type",
            issue_type_name="Analysis",
            created_at_jira=datetime(2026, 5, 1, tzinfo=timezone.utc),
            resolved_at_jira=datetime(2026, 5, 3, tzinfo=timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        older_issue = JiraIssue(
            jira_issue_id="avp-older",
            key="BM-3",
            project_id=bm.id,
            issue_type_id="analysis-type",
            issue_type_name="Analysis",
            created_at_jira=datetime(2025, 1, 1, tzinfo=timezone.utc),
            resolved_at_jira=datetime(2026, 5, 3, tzinfo=timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add_all([root, issue, standalone_issue, older_issue])
        db.flush()
        feature_root = JiraFeatureRoot(
            root_issue_id=root.id,
            root_key=root.key,
            root_project_key="PMGT",
            root_issue_type_name="Epic",
            name="PMGT feature",
            detection_rule="test",
        )
        db.add(feature_root)
        db.flush()
        db.add_all(
            [
                JiraIssueDetail(issue_id=root.id, team_name="Team Tantrum"),
                JiraIssueDetail(issue_id=standalone_issue.id, team_name="Team World"),
                JiraFeatureMembership(
                    feature_root_id=feature_root.id,
                    member_issue_id=issue.id,
                    depth=1,
                    path_issue_keys=[root.key, issue.key],
                    inclusion_reason="test",
                ),
                JiraIssueStatusTransition(
                    issue_id=issue.id,
                    jira_history_id="h1",
                    history_item_index=0,
                    changed_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
                    to_status_name="In Progress",
                ),
                JiraIssueStatusTransition(
                    issue_id=issue.id,
                    jira_history_id="h2",
                    history_item_index=0,
                    changed_at=datetime(2026, 5, 2, tzinfo=timezone.utc),
                    to_status_name="Ready for code review",
                ),
                JiraIssueStatusTransition(
                    issue_id=standalone_issue.id,
                    jira_history_id="h3",
                    history_item_index=0,
                    changed_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
                    to_status_name="In Progress",
                ),
                JiraIssueStatusTransition(
                    issue_id=standalone_issue.id,
                    jira_history_id="h4",
                    history_item_index=0,
                    changed_at=datetime(2026, 5, 2, tzinfo=timezone.utc),
                    to_status_name="Reopened",
                ),
                JiraIssueStatusTransition(
                    issue_id=older_issue.id,
                    jira_history_id="h5",
                    history_item_index=0,
                    changed_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
                    to_status_name="In Progress",
                ),
                JiraIssueStatusTransition(
                    issue_id=older_issue.id,
                    jira_history_id="h6",
                    history_item_index=0,
                    changed_at=datetime(2026, 5, 2, tzinfo=timezone.utc),
                    to_status_name="Reopened",
                ),
                JiraUserRoleAssignment(
                    user_account_id="dev-1",
                    user_email="dev@example.com",
                    display_name="Dev One",
                    role_name="Developer",
                    team_name="Team Tantrum",
                    valid_from=date(2020, 1, 1),
                ),
                JiraUserRoleAssignment(
                    user_account_id="dev-2",
                    user_email="dev2@example.com",
                    display_name="Dev Two",
                    role_name="Developer",
                    team_name="Cosmic Coders",
                    valid_from=date(2026, 5, 26),
                ),
                JiraUserRoleAssignment(
                    user_account_id="dev-3",
                    user_email="dev3@example.com",
                    display_name="Dev Three",
                    role_name="Developer",
                    team_name="Team World",
                    valid_from=date(2020, 1, 1),
                ),
                JiraWorklog(
                    issue_id=issue.id,
                    jira_worklog_id="avp-wl",
                    author_account_id="dev-1",
                    author_email_address="dev@example.com",
                    started_at=datetime(2026, 5, 1, 12, tzinfo=timezone.utc),
                    time_spent_seconds=3600,
                ),
                JiraWorklog(
                    issue_id=standalone_issue.id,
                    jira_worklog_id="avp-wl-standalone",
                    author_account_id="dev-2",
                    author_email_address="dev2@example.com",
                    started_at=datetime(2026, 5, 1, 12, tzinfo=timezone.utc),
                    time_spent_seconds=3600,
                ),
                JiraWorklog(
                    issue_id=older_issue.id,
                    jira_worklog_id="avp-wl-older",
                    author_account_id="dev-3",
                    author_email_address="dev3@example.com",
                    started_at=datetime(2026, 5, 1, 12, tzinfo=timezone.utc),
                    time_spent_seconds=3600,
                ),
            ]
        )
        db.commit()

    res = client.get(
        "/api/jira-analytics/workflow/active-vs-passive",
        params={"from": "2026-05-01", "to": "2026-05-02"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["filters"]["date_basis"] == "issue_created"
    assert body["filters"]["available_teams"] == ["Cosmic Coders", "Team Tantrum"]
    assert body["table"] == [
        {
            "workflow": "Standard Plunet Workflow",
            "team": "Cosmic Coders",
            "Active Work": 24.0,
            "Dev Queue": 24.0,
        },
        {
            "workflow": "Standard Plunet Workflow",
            "team": "Team Tantrum",
            "Active Work": 24.0,
            "Dev Queue": 24.0,
        }
    ]
    standard = next(
        workflow
        for workflow in body["filters"]["main_workflows"]
        if workflow["label"] == "Standard Plunet Workflow"
    )
    assert standard["label"] == "Standard Plunet Workflow"
    assert standard["issue_type_options"] == ["Analysis"]
    assert standard["data_points"][0]["confidence"] == "definite"
    assert {point["team"] for point in standard["data_points"]} == {
        "Cosmic Coders",
        "Team Tantrum",
    }
    assert standard["timeline_points"][0]["status"] == "In Progress"
    assert standard["timeline_points"][0]["interval_start"] == "2026-05-01T00:00:00+00:00"
    empty_workflows = [
        workflow
        for workflow in body["filters"]["main_workflows"]
        if workflow["label"] != "Standard Plunet Workflow"
    ]
    assert all(workflow["data_points"] == [] for workflow in empty_workflows)

    filtered = client.get(
        "/api/jira-analytics/workflow/active-vs-passive",
        params={"from": "2026-05-01", "to": "2026-05-02", "issueType": "Bug"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["table"] == []


def test_active_vs_passive_trend_splits_interval_time_by_quarter_and_filters_team(
    client: TestClient,
) -> None:
    with Session(database.get_engine()) as db:
        project = JiraProject(jira_project_id="avpt-bm", key="BM", name="Business Manager")
        db.add(project)
        db.flush()
        workflow = JiraWorkflow(
            jira_entity_id="wf-standard-trend",
            name="Standard Plunet Workflow",
            status_order_json=["In Progress", "Ready for code review", "Ready for QA"],
        )
        db.add(workflow)
        db.flush()
        db.add(
            JiraProjectWorkflowMapping(
                project_id=project.id,
                issue_type_id="analysis-trend",
                issue_type_name="Analysis",
                workflow_id=workflow.id,
            )
        )
        tantrum_issue = JiraIssue(
            jira_issue_id="avpt-1",
            key="BM-TREND-1",
            project_id=project.id,
            issue_type_id="analysis-trend",
            issue_type_name="Analysis",
            created_at_jira=datetime(2026, 1, 1, tzinfo=timezone.utc),
            resolved_at_jira=datetime(2026, 4, 5, tzinfo=timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        world_issue = JiraIssue(
            jira_issue_id="avpt-2",
            key="BM-TREND-2",
            project_id=project.id,
            issue_type_id="analysis-trend",
            issue_type_name="Analysis",
            created_at_jira=datetime(2026, 4, 1, tzinfo=timezone.utc),
            resolved_at_jira=datetime(2026, 4, 3, tzinfo=timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add_all([tantrum_issue, world_issue])
        db.flush()
        db.add_all(
            [
                JiraIssueStatusTransition(
                    issue_id=tantrum_issue.id,
                    jira_history_id="avpt-h1",
                    history_item_index=0,
                    changed_at=datetime(2026, 3, 31, tzinfo=timezone.utc),
                    to_status_name="In Progress",
                ),
                JiraIssueStatusTransition(
                    issue_id=tantrum_issue.id,
                    jira_history_id="avpt-h2",
                    history_item_index=0,
                    changed_at=datetime(2026, 4, 2, tzinfo=timezone.utc),
                    to_status_name="Ready for code review",
                ),
                JiraIssueStatusTransition(
                    issue_id=tantrum_issue.id,
                    jira_history_id="avpt-h3",
                    history_item_index=0,
                    changed_at=datetime(2026, 4, 5, tzinfo=timezone.utc),
                    to_status_name="Done",
                ),
                JiraIssueStatusTransition(
                    issue_id=world_issue.id,
                    jira_history_id="avpt-h4",
                    history_item_index=0,
                    changed_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
                    to_status_name="In Progress",
                ),
                JiraIssueStatusTransition(
                    issue_id=world_issue.id,
                    jira_history_id="avpt-h5",
                    history_item_index=0,
                    changed_at=datetime(2026, 4, 2, tzinfo=timezone.utc),
                    to_status_name="Ready for QA",
                ),
                JiraIssueStatusTransition(
                    issue_id=world_issue.id,
                    jira_history_id="avpt-h6",
                    history_item_index=0,
                    changed_at=datetime(2026, 4, 3, tzinfo=timezone.utc),
                    to_status_name="Done",
                ),
                JiraUserRoleAssignment(
                    user_account_id="trend-tt",
                    user_email="trend.tt@example.com",
                    display_name="Trend Tantrum",
                    role_name="Developer",
                    team_name="Team Tantrum",
                    valid_from=date(2020, 1, 1),
                ),
                JiraUserRoleAssignment(
                    user_account_id="trend-tw",
                    user_email="trend.tw@example.com",
                    display_name="Trend World",
                    role_name="Developer",
                    team_name="Team World",
                    valid_from=date(2020, 1, 1),
                ),
                JiraWorklog(
                    issue_id=tantrum_issue.id,
                    jira_worklog_id="avpt-wl-tt",
                    author_account_id="trend-tt",
                    author_email_address="trend.tt@example.com",
                    started_at=datetime(2026, 4, 1, 12, tzinfo=timezone.utc),
                    time_spent_seconds=3600,
                ),
                JiraWorklog(
                    issue_id=world_issue.id,
                    jira_worklog_id="avpt-wl-tw",
                    author_account_id="trend-tw",
                    author_email_address="trend.tw@example.com",
                    started_at=datetime(2026, 4, 1, 12, tzinfo=timezone.utc),
                    time_spent_seconds=3600,
                ),
            ]
        )
        db.commit()

    res = client.get(
        "/api/jira-analytics/workflow/active-vs-passive-trend",
        params={"from": "2026-01-01", "to": "2026-06-30"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["filters"]["date_basis"] == "status_interval_overlap"
    assert body["filters"]["grain"] == "quarter"
    assert body["series"] == [
        {
            "period": "2026-Q1",
            "quarter": "Q1 2026",
            "quarter_start": "2026-01-01",
            "quarter_end": "2026-03-31",
            "active_hours": 24.0,
            "passive_hours": 0.0,
            "product_queue_hours": 0.0,
            "dev_queue_hours": 0.0,
            "qa_queue_hours": 0.0,
            "total_hours": 24.0,
            "passive_share": 0.0,
            "passive_share_delta": None,
            "Team Tantrum__passive_share": 0.0,
            "Team Tantrum__active_hours": 24.0,
            "Team Tantrum__passive_hours": 0.0,
        },
        {
            "period": "2026-Q2",
            "quarter": "Q2 2026",
            "quarter_start": "2026-04-01",
            "quarter_end": "2026-06-30",
            "active_hours": 48.0,
            "passive_hours": 96.0,
            "product_queue_hours": 0.0,
            "dev_queue_hours": 72.0,
            "qa_queue_hours": 24.0,
            "total_hours": 144.0,
            "passive_share": 0.6667,
            "passive_share_delta": 0.6667,
            "Team Tantrum__passive_share": 0.75,
            "Team Tantrum__active_hours": 24.0,
            "Team Tantrum__passive_hours": 72.0,
            "Team World__passive_share": 0.5,
            "Team World__active_hours": 24.0,
            "Team World__passive_hours": 24.0,
        },
    ]
    assert body["summary"]["latest_passive_share"] == 0.6667
    assert body["summary"]["passive_share_delta"] == 0.6667
    q2_tantrum = next(
        row
        for row in body["table"]
        if row["period"] == "2026-Q2" and row["team"] == "Team Tantrum"
    )
    assert q2_tantrum["passive_share"] == 0.75
    assert q2_tantrum["passive_share_delta"] == 0.75

    filtered = client.get(
        "/api/jira-analytics/workflow/active-vs-passive-trend",
        params={"from": "2026-01-01", "to": "2026-06-30", "team": "Team World"},
    )
    assert filtered.status_code == 200
    filtered_body = filtered.json()
    assert filtered_body["filters"]["available_teams"] == ["Team Tantrum", "Team World"]
    assert filtered_body["filters"]["available_workflows"] == ["Standard Plunet Workflow"]
    assert filtered_body["table"] == [
        {
            "period": "2026-Q2",
            "quarter": "Q2 2026",
            "quarter_start": "2026-04-01",
            "quarter_end": "2026-06-30",
            "team": "Team World",
            "workflow": "Standard Plunet Workflow",
            "active_hours": 24.0,
            "passive_hours": 24.0,
            "product_queue_hours": 0.0,
            "dev_queue_hours": 0.0,
            "qa_queue_hours": 24.0,
            "total_hours": 48.0,
            "passive_share": 0.5,
            "passive_share_delta": None,
            "total_hours_delta": None,
        }
    ]


def test_bound_quarter_period_defaults_and_caps_span() -> None:
    from_date, to_date = bound_quarter_period(None, date(2026, 5, 15))
    assert to_date == date(2026, 5, 15)
    assert from_date == date(2025, 7, 1)

    capped_from, capped_to = bound_quarter_period(date(2010, 1, 1), date(2026, 5, 15))
    assert capped_to == date(2026, 5, 15)
    assert capped_from == date(2023, 7, 1)


def test_planned_vs_unplanned_uses_heatmap_team_assignment_and_roadmap_focus(client: TestClient) -> None:
    with Session(database.get_engine()) as db:
        project = JiraProject(jira_project_id="pvu-bm", key="BM", name="Business Manager")
        db.add(project)
        db.flush()
        issue = JiraIssue(
            jira_issue_id="pvu-1",
            key="BM-10",
            project_id=project.id,
            issue_type_name="Task",
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(issue)
        db.flush()
        db.add(
            JiraUserRoleAssignment(
                user_account_id="dev-1",
                user_email="dev.one@example.com",
                display_name="Dev One",
                role_name="Developer",
                team_name="Team World",
                valid_from=date(2020, 1, 1),
            )
        )
        db.add_all(
            [
                MonthlyAllocatedEffort(
                    period_month=date(2026, 5, 1),
                    topic_type="feature",
                    issue_id=issue.id,
                    issue_key=issue.key,
                    source_user_email="dev-1",
                    source_display_name="Dev One",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=Decimal("30"),
                    rule_snapshot_json={},
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 5, 1),
                    topic_type="tech_support",
                    issue_id=issue.id,
                    issue_key=issue.key,
                    source_user_email="dev-1",
                    source_display_name="Dev One",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=Decimal("10"),
                    rule_snapshot_json={},
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 4, 1),
                    topic_type="feature",
                    issue_id=issue.id,
                    issue_key=issue.key,
                    source_user_email="dev-1",
                    source_display_name="Dev One",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=Decimal("20"),
                    rule_snapshot_json={},
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 4, 1),
                    topic_type="unassigned_bug",
                    issue_id=issue.id,
                    issue_key=issue.key,
                    source_user_email="dev-1",
                    source_display_name="Dev One",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=Decimal("5"),
                    rule_snapshot_json={},
                ),
            ]
        )
        db.commit()

    res = client.get(
        "/api/jira-analytics/teams/planned-vs-unplanned",
        params={"from": "2026-04-01", "to": "2026-05-31"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["filters"]["available_teams"] == ["Team World"]
    assert body["table"] == [
        {
            "team": "Team World",
            "month": "2026-05-01",
            "roadmap_hours": 30.0,
            "continuous_improvement_hours": 10.0,
            "roadmap_focus": 0.75,
        },
        {
            "team": "Team World",
            "month": "2026-04-01",
            "roadmap_hours": 20.0,
            "continuous_improvement_hours": 5.0,
            "roadmap_focus": 0.8,
        },
    ]
    assert body["series"] == [
        {"period": "2026-04-01", "Team World": 0.8},
        {"period": "2026-05-01", "Team World": 0.75},
    ]


def test_real_interruption_ratio_classifies_started_candidate_issues(client: TestClient) -> None:
    with Session(database.get_engine()) as db:
        project = JiraProject(jira_project_id="rir-bm", key="BM", name="Business Manager")
        db.add(project)
        db.flush()
        interrupted = JiraIssue(
            jira_issue_id="rir-1",
            key="BM-101",
            project_id=project.id,
            issue_type_name="Bug",
            summary="Escalated support issue",
            priority_name="High",
            created_at_jira=datetime(2026, 5, 1, tzinfo=timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
            raw_issue_json={
                "changelog": {
                    "histories": [
                        {
                            "created": "2026-05-10T10:00:00+00:00",
                            "items": [
                                {
                                    "field": "priority",
                                    "fromString": "Low",
                                    "toString": "High",
                                }
                            ],
                        }
                    ]
                }
            },
        )
        planned = JiraIssue(
            jira_issue_id="rir-2",
            key="BM-102",
            project_id=project.id,
            issue_type_name="Task",
            summary="Older small feature",
            priority_name="Low",
            created_at_jira=datetime(2025, 1, 1, tzinfo=timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        roadmap = JiraIssue(
            jira_issue_id="rir-3",
            key="BM-103",
            project_id=project.id,
            issue_type_name="Story",
            summary="Roadmap issue",
            priority_name="Medium",
            created_at_jira=datetime(2026, 4, 1, tzinfo=timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add_all([interrupted, planned, roadmap])
        db.flush()
        db.add(
            JiraUserRoleAssignment(
                user_account_id="dev-rir",
                user_email="dev.rir@example.com",
                display_name="Dev Rir",
                role_name="Developer",
                team_name="Team Tantrum",
                valid_from=date(2020, 1, 1),
            )
        )
        db.add_all(
            [
                JiraIssueStatusTransition(
                    issue_id=interrupted.id,
                    jira_history_id="rir-h1",
                    history_item_index=0,
                    changed_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
                    to_status_name="In Progress",
                ),
                JiraIssueStatusTransition(
                    issue_id=planned.id,
                    jira_history_id="rir-h2",
                    history_item_index=0,
                    changed_at=datetime(2026, 5, 16, tzinfo=timezone.utc),
                    to_status_name="Development",
                ),
                JiraIssueStatusTransition(
                    issue_id=roadmap.id,
                    jira_history_id="rir-h3",
                    history_item_index=0,
                    changed_at=datetime(2026, 5, 17, tzinfo=timezone.utc),
                    to_status_name="Development",
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 5, 1),
                    topic_type="tech_support",
                    issue_id=interrupted.id,
                    issue_key=interrupted.key,
                    source_user_email="dev-rir",
                    source_display_name="Dev Rir",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=Decimal("8"),
                    rule_snapshot_json={},
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 5, 1),
                    topic_type="issue_without_feature",
                    issue_id=planned.id,
                    issue_key=planned.key,
                    source_user_email="dev-rir",
                    source_display_name="Dev Rir",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=Decimal("5"),
                    rule_snapshot_json={},
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 5, 1),
                    topic_type="feature",
                    issue_id=roadmap.id,
                    issue_key=roadmap.key,
                    source_user_email="dev-rir",
                    source_display_name="Dev Rir",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=Decimal("12"),
                    rule_snapshot_json={},
                ),
            ]
        )
        db.commit()

    res = client.get(
        "/api/jira-analytics/teams/real-interruption-ratio",
        params={"from": "2026-05-01", "to": "2026-05-31"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["table"] == [
        {
            "team": "Team Tantrum",
            "month": "2026-05-01",
            "started_roadmap_issues": 1,
            "interrupting_issues": 1,
            "maybe_interrupted_issues": 0,
            "interruption_ratio": 0.5,
            "started_roadmap_hours": 12.0,
            "interrupting_hours": 8.0,
            "time_interruption_ratio": 0.4,
        }
    ]
    assert body["series"] == [{"period": "2026-05-01", "Team Tantrum": 0.5}]
    assert body["filters"]["time_series"] == [{"period": "2026-05-01", "Team Tantrum": 0.4}]
    issue_rows = body["filters"]["issue_rows"]
    interrupted_row = next(row for row in issue_rows if row["issue_key"] == "BM-101")
    assert interrupted_row["classification"] == "interrupted"
    assert interrupted_row["confidence"] == "high"
    assert "bug_created_within_16_weeks_before_start" in interrupted_row["signals"]
    assert "priority_increased_within_8_weeks_before_start" in interrupted_row["signals"]


def test_throughput_uses_dev_assignment_team_from_issue_worklogs(client: TestClient) -> None:
    with Session(database.get_engine()) as db:
        project = JiraProject(jira_project_id="thr-bm", key="BM", name="Business Manager")
        db.add(project)
        db.flush()
        assignee = JiraUser(
            account_id="assignee-1",
            email_address="assignee@example.com",
            display_name="Assignee User",
        )
        dev = JiraUser(
            account_id="dev-1",
            email_address="dev@example.com",
            display_name="Dev Worker",
        )
        db.add_all([assignee, dev])
        db.flush()
        issue = JiraIssue(
            jira_issue_id="thr-1",
            key="BM-501",
            project_id=project.id,
            issue_type_name="Task",
            assignee_user_id=assignee.id,
            resolved_at_jira=datetime(2026, 5, 10, tzinfo=timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(issue)
        db.flush()
        db.add_all(
            [
                JiraUserRoleAssignment(
                    user_account_id="assignee-1",
                    user_email="assignee@example.com",
                    display_name="Assignee User",
                    role_name="Product Manager",
                    team_name="Team Tantrum",
                    valid_from=date(2020, 1, 1),
                ),
                JiraUserRoleAssignment(
                    user_account_id="dev-1",
                    user_email="dev@example.com",
                    display_name="Dev Worker",
                    role_name="Developer",
                    team_name="Team World",
                    valid_from=date(2020, 1, 1),
                ),
                JiraWorklog(
                    issue_id=issue.id,
                    jira_worklog_id="thr-wl-1",
                    author_account_id="dev-1",
                    author_email_address="dev@example.com",
                    author_display_name="Dev Worker",
                    started_at=datetime(2026, 5, 9, 9, 0, tzinfo=timezone.utc),
                    time_spent_seconds=5400,
                ),
            ]
        )
        db.commit()

    res = client.get(
        "/api/jira-analytics/teams/throughput-stability",
        params={"from": "2026-05-01", "to": "2026-05-31"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["table"] == [
        {
            "team": "Team World",
            "avg_done_per_week": 1.0,
            "stddev": 0.0,
            "predictability": 1.0,
        }
    ]


def test_throughput_excludes_unknown_and_legacy_teams(client: TestClient) -> None:
    with Session(database.get_engine()) as db:
        project = JiraProject(jira_project_id="thr-ex", key="BM", name="Business Manager")
        db.add(project)
        db.flush()
        unknown_assignee = JiraUser(
            account_id="unknown-1",
            email_address="unknown@example.com",
            display_name="Unknown Assignee",
        )
        legacy_dev = JiraUser(
            account_id="legacy-1",
            email_address="legacy@example.com",
            display_name="Legacy Dev",
        )
        db.add_all([unknown_assignee, legacy_dev])
        db.flush()
        db.add_all(
            [
                JiraIssue(
                    jira_issue_id="thr-unknown",
                    key="BM-901",
                    project_id=project.id,
                    issue_type_name="Task",
                    assignee_user_id=unknown_assignee.id,
                    resolved_at_jira=datetime(2026, 5, 10, tzinfo=timezone.utc),
                    last_seen_at=datetime.now(timezone.utc),
                ),
                JiraIssue(
                    jira_issue_id="thr-legacy",
                    key="BM-902",
                    project_id=project.id,
                    issue_type_name="Task",
                    assignee_user_id=legacy_dev.id,
                    resolved_at_jira=datetime(2026, 5, 11, tzinfo=timezone.utc),
                    last_seen_at=datetime.now(timezone.utc),
                ),
            ]
        )
        db.flush()
        db.add(
            JiraUserRoleAssignment(
                user_account_id="legacy-1",
                user_email="legacy@example.com",
                display_name="Legacy Dev",
                role_name="Developer",
                team_name="legacy",
                valid_from=date(2020, 1, 1),
            )
        )
        db.commit()

    res = client.get(
        "/api/jira-analytics/teams/throughput-stability",
        params={"from": "2026-05-01", "to": "2026-05-31"},
    )

    assert res.status_code == 200
    teams = {row["team"] for row in res.json()["table"]}
    assert "Unknown" not in teams
    assert "legacy" not in teams


def test_engineering_health_combines_components_and_honors_team_filter(client: TestClient) -> None:
    with Session(database.get_engine()) as db:
        project = JiraProject(jira_project_id="ehi-bm", key="BM", name="Business Manager")
        db.add(project)
        db.flush()
        roadmap = JiraIssue(
            jira_issue_id="ehi-roadmap",
            key="BM-601",
            project_id=project.id,
            issue_type_name="Story",
            resolved_at_jira=datetime(2026, 5, 10, tzinfo=timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        support = JiraIssue(
            jira_issue_id="ehi-support",
            key="BM-602",
            project_id=project.id,
            issue_type_name="Task",
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add_all([roadmap, support])
        db.flush()
        user = JiraUser(
            account_id="ehi-dev",
            display_name="Health Dev",
            email_address="ehi.dev@example.com",
        )
        db.add(user)
        db.flush()
        db.add(
            JiraUserRoleAssignment(
                jira_user_id=user.id,
                user_account_id="ehi-dev",
                user_email="ehi.dev@example.com",
                display_name="Health Dev",
                role_name="Developer",
                team_name="Team World",
                valid_from=date(2020, 1, 1),
            )
        )
        db.add_all(
            [
                JiraWorklog(
                    issue_id=roadmap.id,
                    jira_worklog_id="ehi-wl",
                    author_account_id="ehi-dev",
                    author_email_address="ehi.dev@example.com",
                    author_display_name="Health Dev",
                    started_at=datetime(2026, 5, 9, 9, 0, tzinfo=timezone.utc),
                    time_spent_seconds=3600,
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 5, 1),
                    topic_type="feature",
                    issue_id=roadmap.id,
                    issue_key=roadmap.key,
                    source_user_email="ehi-dev",
                    source_display_name="Health Dev",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=Decimal("30"),
                    rule_snapshot_json={},
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 5, 1),
                    topic_type="tech_support",
                    issue_id=support.id,
                    issue_key=support.key,
                    source_user_email="ehi-dev",
                    source_display_name="Health Dev",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=Decimal("10"),
                    rule_snapshot_json={},
                ),
                JiraUserMonthlyHrworksHours(
                    jira_user_id=user.id,
                    month_start=date(2026, 5, 1),
                    month_end=date(2026, 5, 31),
                    planned_working_hours=Decimal("160"),
                    clocked_working_hours=Decimal("150"),
                ),
                MonthlyTopicEffortBase(
                    period_month=date(2026, 5, 1),
                    issue_id=roadmap.id,
                    issue_key=roadmap.key,
                    user_account_id="ehi-dev",
                    display_name="Health Dev",
                    role_name="Developer",
                    topic_type="feature",
                    direct_hours=Decimal("40"),
                ),
            ]
        )
        db.commit()

    res = client.get(
        "/api/jira-analytics/executive/engineering-health",
        params={"from": "2026-05-01", "to": "2026-05-31", "team": "Team World"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["filters"]["from"] == "2026-05-01"
    assert body["filters"]["to"] == "2026-05-31"
    assert body["filters"]["focused_teams"] == ["Team World"]
    assert body["filters"]["weights"]["focus_health"] == 0.2
    assert body["series"] == [{"period": "2026-05-01", "Team World": 87.5}]
    assert body["summary"]["average_health_index"] == 87.5
    assert body["table"] == [
        {
            "team": "Team World",
            "month": "2026-05-01",
            "health_index": 87.5,
            "confidence": 0.6,
            "biggest_drag": "interruption_health",
            "second_drag": "focus_health",
            "flow_efficiency": None,
            "focus_health": 87.5,
            "interruption_health": 75.0,
            "execution_predictability": 100.0,
            "work_shape_health": None,
            "roadmap_hours": 30.0,
            "continuous_improvement_hours": 10.0,
            "roadmap_focus": 0.75,
            "interruption_ratio": 0.25,
            "time_interruption_ratio": None,
            "interrupting_hours": 10.0,
            "interruption_source": "roadmap_focus_fallback",
            "avg_done_per_week": 1.0,
            "throughput_stddev": 0.0,
            "throughput_predictability": 1.0,
            "dev_workforce_strength_hours": 160.0,
            "qa_workforce_strength_hours": 0.0,
            "workforce_strength_hours": 160.0,
            "dev_booked_hours": 40.0,
            "qa_booked_hours": 0.0,
            "booked_hours": 40.0,
            "dev_utilization_ratio": 0.25,
            "qa_utilization_ratio": None,
            "utilization_ratio": 0.25,
        }
    ]


def test_engineering_health_includes_freedevs_when_present(client: TestClient) -> None:
    with Session(database.get_engine()) as db:
        project = JiraProject(jira_project_id="ehi-free-bm", key="BM", name="Business Manager")
        db.add(project)
        db.flush()
        issue = JiraIssue(
            jira_issue_id="ehi-free-issue",
            key="BM-701",
            project_id=project.id,
            issue_type_name="Story",
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(issue)
        db.flush()
        db.add(
            JiraUserRoleAssignment(
                user_account_id="free-dev",
                user_email="free.dev@example.com",
                display_name="Free Dev",
                role_name="Developer",
                team_name="FreeDevs",
                valid_from=date(2020, 1, 1),
            )
        )
        db.add(
            MonthlyAllocatedEffort(
                period_month=date(2026, 5, 1),
                topic_type="feature",
                issue_id=issue.id,
                issue_key=issue.key,
                source_user_email="free-dev",
                source_display_name="Free Dev",
                source_role_name="Developer",
                allocation_kind="direct_worklog",
                hours=Decimal("8"),
                rule_snapshot_json={},
            )
        )
        db.commit()

    res = client.get(
        "/api/jira-analytics/executive/engineering-health",
        params={"from": "2026-05-01", "to": "2026-05-31"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["filters"]["focused_teams"] == [
        "Team Tantrum",
        "Team World",
        "Cosmic Coders",
        "FreeDevs",
    ]
    free_row = next(row for row in body["table"] if row["team"] == "FreeDevs")
    assert free_row["focus_health"] == 100.0
    assert free_row["confidence"] == 0.4
    assert free_row["health_index"] is None


def test_engineering_health_returns_partial_response_when_component_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.jira_analytics.reports import reports_service as reports

    def _boom(*_args, **_kwargs):
        raise RuntimeError("flow query timed out")

    monkeypatch.setattr(reports, "_health_flow_components", _boom)
    res = client.get(
        "/api/jira-analytics/executive/engineering-health",
        params={"from": "2026-05-01", "to": "2026-05-31", "team": "Team Tantrum"},
    )
    assert res.status_code == 200
    body = res.json()
    assert any("flow_efficiency" in warning for warning in body["filters"]["component_warnings"])


def test_engineering_health_reports_missing_data_with_low_confidence(client: TestClient) -> None:
    res = client.get(
        "/api/jira-analytics/executive/engineering-health",
        params={"from": "2026-05-01", "to": "2026-05-31", "team": "Team Tantrum"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["table"] == [
        {
            "team": "Team Tantrum",
            "month": "2026-05-01",
            "health_index": None,
            "confidence": 0.0,
            "biggest_drag": None,
            "second_drag": None,
            "flow_efficiency": None,
            "focus_health": None,
            "interruption_health": None,
            "execution_predictability": None,
            "work_shape_health": None,
            "dev_workforce_strength_hours": 0.0,
            "qa_workforce_strength_hours": 0.0,
            "workforce_strength_hours": 0.0,
            "dev_booked_hours": 0.0,
            "qa_booked_hours": 0.0,
            "booked_hours": 0.0,
            "dev_utilization_ratio": None,
            "qa_utilization_ratio": None,
            "utilization_ratio": None,
        }
    ]
    assert body["summary"]["data_coverage"] == 0.0


def test_engineering_health_calculates_flow_and_throughput_by_month(
    client: TestClient,
) -> None:
    with Session(database.get_engine()) as db:
        project = JiraProject(jira_project_id="ehi-month-bm", key="BM", name="Business Manager")
        db.add(project)
        db.flush()
        workflow = JiraWorkflow(
            jira_entity_id="ehi-month-wf",
            name="Standard Plunet Workflow",
            status_order_json=["In Progress", "Ready for code review", "Code Review", "Ready for QA"],
        )
        db.add(workflow)
        db.flush()
        db.add(
            JiraProjectWorkflowMapping(
                project_id=project.id,
                issue_type_id="analysis-type",
                issue_type_name="Analysis",
                workflow_id=workflow.id,
            )
        )
        db.add(
            JiraUserRoleAssignment(
                user_account_id="month-dev",
                user_email="month.dev@example.com",
                display_name="Month Dev",
                role_name="Developer",
                team_name="Team World",
                valid_from=date(2020, 1, 1),
            )
        )

        def add_issue(
            key: str,
            created: datetime,
            resolved: datetime,
            transitions: list[tuple[str, datetime]],
        ) -> JiraIssue:
            issue = JiraIssue(
                jira_issue_id=f"ehi-{key}",
                key=key,
                project_id=project.id,
                issue_type_id="analysis-type",
                issue_type_name="Analysis",
                created_at_jira=created,
                resolved_at_jira=resolved,
                last_seen_at=datetime.now(timezone.utc),
            )
            db.add(issue)
            db.flush()
            db.add(
                JiraWorklog(
                    issue_id=issue.id,
                    jira_worklog_id=f"wl-{key}",
                    author_account_id="month-dev",
                    author_email_address="month.dev@example.com",
                    author_display_name="Month Dev",
                    started_at=resolved,
                    time_spent_seconds=3600,
                )
            )
            for idx, (status, changed_at) in enumerate(transitions):
                db.add(
                    JiraIssueStatusTransition(
                        issue_id=issue.id,
                        jira_history_id=f"h-{key}-{idx}",
                        history_item_index=0,
                        changed_at=changed_at,
                        to_status_name=status,
                    )
                )
            return issue

        april_flow = add_issue(
            "BM-801",
            datetime(2026, 4, 1, tzinfo=timezone.utc),
            datetime(2026, 4, 3, tzinfo=timezone.utc),
            [
                ("In Progress", datetime(2026, 4, 1, tzinfo=timezone.utc)),
                ("Ready for code review", datetime(2026, 4, 2, tzinfo=timezone.utc)),
            ],
        )
        may_flow = add_issue(
            "BM-802",
            datetime(2026, 5, 1, tzinfo=timezone.utc),
            datetime(2026, 5, 5, tzinfo=timezone.utc),
            [
                ("In Progress", datetime(2026, 5, 1, tzinfo=timezone.utc)),
                ("Code Review", datetime(2026, 5, 2, tzinfo=timezone.utc)),
                ("Ready for QA", datetime(2026, 5, 4, tzinfo=timezone.utc)),
            ],
        )
        add_issue("BM-803", datetime(2026, 4, 2, tzinfo=timezone.utc), datetime(2026, 4, 4, tzinfo=timezone.utc), [])
        add_issue("BM-804", datetime(2026, 4, 10, tzinfo=timezone.utc), datetime(2026, 4, 10, tzinfo=timezone.utc), [])
        add_issue("BM-805", datetime(2026, 5, 12, tzinfo=timezone.utc), datetime(2026, 5, 12, tzinfo=timezone.utc), [])
        db.add_all(
            [
                MonthlyAllocatedEffort(
                    period_month=date(2026, 4, 1),
                    topic_type="feature",
                    issue_id=april_flow.id,
                    issue_key=april_flow.key,
                    source_user_email="month-dev",
                    source_display_name="Month Dev",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=Decimal("20"),
                    rule_snapshot_json={},
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 4, 1),
                    topic_type="tech_support",
                    issue_id=april_flow.id,
                    issue_key=april_flow.key,
                    source_user_email="month-dev",
                    source_display_name="Month Dev",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=Decimal("10"),
                    rule_snapshot_json={},
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 5, 1),
                    topic_type="feature",
                    issue_id=may_flow.id,
                    issue_key=may_flow.key,
                    source_user_email="month-dev",
                    source_display_name="Month Dev",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=Decimal("40"),
                    rule_snapshot_json={},
                ),
            ]
        )
        db.commit()

    res = client.get(
        "/api/jira-analytics/executive/engineering-health",
        params={"from": "2026-04-01", "to": "2026-05-31", "team": "Team World"},
    )

    assert res.status_code == 200
    rows = {row["month"]: row for row in res.json()["table"]}
    assert rows["2026-04-01"]["flow_efficiency"] == 50.0
    assert rows["2026-05-01"]["flow_efficiency"] == 75.0
    assert rows["2026-04-01"]["execution_predictability"] == 66.67
    assert rows["2026-05-01"]["execution_predictability"] == 100.0
    assert rows["2026-04-01"]["flow_efficiency"] != rows["2026-05-01"]["flow_efficiency"]
    assert (
        rows["2026-04-01"]["execution_predictability"]
        != rows["2026-05-01"]["execution_predictability"]
    )


def test_allocation_rebuild_defaults_to_latest_worklog_month(client: TestClient) -> None:
    with Session(database.get_engine()) as db:
        project = JiraProject(jira_project_id="allocation-bm", key="BM", name="Business Manager")
        db.add(project)
        db.flush()
        issue = JiraIssue(
            jira_issue_id="10001",
            key="BM-10001",
            project_id=project.id,
            issue_type_name="Story",
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(issue)
        db.flush()
        db.add_all(
            [
                JiraWorklog(
                    issue_id=issue.id,
                    jira_worklog_id="wl-old",
                    author_account_id="acc-1",
                    author_display_name="User One",
                    started_at=datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc),
                    time_spent_seconds=3600,
                ),
                JiraWorklog(
                    issue_id=issue.id,
                    jira_worklog_id="wl-new",
                    author_account_id="acc-1",
                    author_display_name="User One",
                    started_at=datetime(2026, 5, 5, 10, 0, tzinfo=timezone.utc),
                    time_spent_seconds=3600,
                ),
            ]
        )
        db.commit()

    res = client.post("/api/jira-analytics/allocation/rebuild", params={"all_periods": "false"})

    assert res.status_code == 200
    assert res.json()["periods"] == ["2026-05-01"]


def test_status_waiting_time_endpoint(client: TestClient) -> None:
    now = datetime.now(timezone.utc)
    with Session(database.get_engine()) as db:
        project = JiraProject(jira_project_id="sw-bm", key="BM", name="Business Manager")
        db.add(project)
        db.flush()
        workflow = JiraWorkflow(
            jira_entity_id="sw-wf",
            name="Standard Plunet Workflow",
            status_order_json=["Backlog", "In Progress"],
        )
        db.add(workflow)
        db.flush()
        workflow_id = workflow.id
        db.add(
            JiraProjectWorkflowMapping(
                project_id=project.id,
                issue_type_id="story",
                workflow_id=workflow_id,
                issue_type_name="Epic",
            )
        )
        issue = JiraIssue(
            jira_issue_id="sw-1",
            key="BM-1",
            project_id=project.id,
            issue_type_id="story",
            issue_type_name="Epic",
            priority_name="High",
            last_seen_at=now,
        )
        db.add(issue)
        db.flush()
        db.add_all(
            [
                JiraIssueStatusTransition(
                    issue_id=issue.id,
                    jira_history_id="sw-h1",
                    history_item_index=0,
                    to_status_name="Backlog",
                    changed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                ),
                JiraIssueStatusTransition(
                    issue_id=issue.id,
                    jira_history_id="sw-h2",
                    history_item_index=0,
                    to_status_name="In Progress",
                    changed_at=datetime(2026, 1, 6, tzinfo=timezone.utc),
                ),
            ]
        )
        db.commit()

    res = client.get(
        "/api/jira-analytics/workflow/status-waiting-time",
        params={"from": "2026-01-01", "to": "2026-01-31", "project_key": "BM"},
    )

    assert res.status_code == 200
    body = res.json()
    main = body["filters"]["main_workflows"]
    assert len(main) == 2
    assert main[0]["catalog_key"] == "plunet_cloud"
    assert main[1]["catalog_key"] == "standard_plunet"
    standard = next(item for item in main if item["catalog_key"] == "standard_plunet")
    assert standard["label"] == "Standard Plunet Workflow"
    assert len(standard["data_points"]) >= 2
    assert standard["data_points"][0]["priority"] == "Major"
    assert standard["data_points"][0]["issue_key"] == "BM-1"
    assert "rows" not in standard or not standard.get("rows")
    assert body["filters"]["other_workflows"] == []
    assert body["filters"]["available_projects"] == [{"key": "BM", "name": "Business Manager"}]
    assert body["filters"]["workflows_synced"] is True
