from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401 - imports all models into Base.metadata
from app.config_schema import ConfigurationSchema
from app.jira_analytics.collector import (
    JiraAnalyticsCounts,
    build_default_jql,
    upsert_issue_payload,
)
from app.jira_analytics.extractors import (
    adf_to_text,
    extract_field_values,
    extract_issue_core,
    extract_issue_detail,
    extract_relations,
    extract_status_transitions,
    extract_worklog,
)
from app.jira_analytics.feature_membership import refresh_feature_memberships
from app.jira_analytics.models import (
    JiraFeatureMembership,
    JiraFeatureRoot,
    JiraIssue,
    JiraIssueDetail,
    JiraIssueRelation,
    JiraProject,
    JiraWorklog,
    MonthlyAllocatedEffort,
)
from app.jira_analytics.reports.reports_service import customer_effort, feature_risk, investment_by_theme, size_vs_speed
from app.models.base import Base


def _fixture(name: str) -> dict:
    path = Path(__file__).resolve().parents[3] / "jira_analytics_requirements" / name
    return json.loads(path.read_text(encoding="utf-8"))


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)
    return maker()


def test_extract_issue_detail_product_discovery_pmgt_fields() -> None:
    detail = extract_issue_detail(
        {
            "customfield_10084": '{"start":"2026-05-01","end":"2026-05-31"}',
            "customfield_10085": '{"start":"2026-06-01","end":"2026-06-30"}',
            "customfield_10079": [{"value": "Cosmic Coders"}],
            "customfield_10185": {"value": "Rest API", "id": "10286"},
        }
    )
    assert detail["start_date"] == date(2026, 5, 1)
    assert detail["promised_delivery_date"] == date(2026, 6, 30)
    assert detail["team_name"] == "Cosmic Coders"
    assert detail["pmgt_product"] == {"value": "Rest API", "id": "10286"}
    assert detail["raw_required_fields_json"]["customfield_10185"] == {
        "value": "Rest API",
        "id": "10286",
    }


def test_default_jira_analytics_jql_includes_global_project_exclusions() -> None:
    config = ConfigurationSchema()
    config.jira.excluded_projects = ["devops", "JIRATESTS"]

    jql = build_default_jql(config, lookback_days=1)

    assert 'project NOT IN ("ACT","DEVOPS","DIM","ITS","JIRATESTS","PLU","SE")' in jql


def test_extract_issue_core_and_required_details_from_sample() -> None:
    raw = _fixture("sample_issue.json")
    fields = raw["fields"]

    core = extract_issue_core(raw)
    assert core is not None
    assert core["key"] == "HUB-533"
    assert core["issue_type_name"] == "Improvement"
    assert core["status_name"] == "Development"
    assert core["parent_key"] == "HUB-535"
    assert "license items" in (core["description_text"] or "")

    detail = extract_issue_detail(fields)
    assert detail["target_branches"] == ["epic branch"]
    assert detail["team_name"] == "Cosmic Coders"
    assert detail["customer_priority"] == "1 - Low"
    assert detail["components"] == ["License server"]


def test_extract_worklog_and_status_transition_from_samples() -> None:
    raw = _fixture("sample_issue.json")
    worklog = raw["fields"]["worklog"]["worklogs"][0]
    parsed = extract_worklog(worklog)
    assert parsed is not None
    assert parsed["jira_worklog_id"] == "85033"
    assert parsed["author_account_id"] == "70121:64f9a91c-becd-4e7e-9a38-5fc66a3da40c"
    assert parsed["time_spent_seconds"] == 21600
    assert parsed["comment_text"] == "research"

    changelog = _fixture("sample_issue_with_changelog.json")
    rows = extract_status_transitions(changelog["changelog"]["histories"])
    assert any(row["from_status_name"] == "Ready for development" for row in rows)
    assert any(row["to_status_name"] == "Development" for row in rows)


def test_extract_field_values_does_not_index_large_json_payloads() -> None:
    raw = _fixture("sample_issue.json")
    rows = extract_field_values(raw["fields"], raw.get("names"), raw.get("schema"))
    by_field = {row["field_id"]: row for row in rows}

    assert by_field["worklog"]["value_json"] is not None
    assert by_field["worklog"]["value_text"] is None


def test_extract_relations_marks_pmgt_issue_links_as_connected() -> None:
    raw = _fixture("sample_issue.json")
    raw["key"] = "IAU-122"
    fields = raw["fields"]
    fields["issuelinks"] = [
        {
            "id": "50001",
            "type": {
                "id": "10000",
                "name": "Relates",
                "inward": "relates to",
                "outward": "relates to",
            },
            "outwardIssue": {"id": "200", "key": "PMGT-12"},
        }
    ]

    relations = extract_relations(raw)
    pmgt_edges = [row for row in relations if row.relation_source == "connected_pmgt_issue"]
    assert len(pmgt_edges) == 1
    assert pmgt_edges[0].target_key == "PMGT-12"


def test_extract_relations_from_parent_subtasks_and_epic_link() -> None:
    raw = _fixture("sample_issue.json")
    fields = raw["fields"]
    fields["customfield_10014"] = "HUB-500"

    relations = extract_relations(raw)
    keys = {(row.relation_source, row.target_key) for row in relations}
    assert ("parent", "HUB-535") in keys
    assert ("subtask", "HUB-549") in keys
    assert ("subtask", "HUB-552") in keys
    assert ("epic_link", "HUB-500") in keys


def test_upsert_issue_resolves_by_jira_issue_id_when_key_changes() -> None:
    """Regression: key-only lookup inserted a duplicate row for an existing jira_issue_id."""
    with _session() as db:
        project = JiraProject(jira_project_id="200", key="BM", name="BM")
        db.add(project)
        db.flush()
        existing = JiraIssue(
            jira_issue_id="88800",
            key="BM-OLD",
            project_id=project.id,
            issue_type_name="Bug",
            summary="Old key",
            last_seen_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
        db.add(existing)
        db.commit()

        raw = {
            "id": "88800",
            "key": "BM-33620",
            "self": "https://plunet.atlassian.net/rest/api/3/issue/88800",
            "fields": {
                "project": {"id": "200", "key": "BM", "name": "BM"},
                "issuetype": {"id": "10011", "name": "Bug", "hierarchyLevel": 0},
                "summary": "Updated summary after key move",
                "status": {
                    "id": "10057",
                    "name": "Ready for development",
                    "statusCategory": {"key": "new", "name": "To Do"},
                },
                "priority": {"id": "10003", "name": "Normal"},
                "created": "2026-04-28T12:24:39.428+0000",
                "updated": "2026-05-28T10:41:24.634+0000",
                "worklog": {"worklogs": []},
            },
        }
        counts = JiraAnalyticsCounts()
        issue = upsert_issue_payload(db, raw, worklogs=[], histories=[], counts=counts)
        db.commit()

        assert issue is not None
        assert issue.jira_issue_id == "88800"
        assert issue.key == "BM-33620"
        assert db.scalar(select(func.count()).select_from(JiraIssue)) == 1
        assert db.scalar(select(JiraIssue).where(JiraIssue.key == "BM-OLD")) is None


def test_upsert_issue_payload_is_idempotent_for_core_rows() -> None:
    raw = _fixture("sample_issue.json")
    changelog = _fixture("sample_issue_with_changelog.json")
    worklogs = raw["fields"]["worklog"]["worklogs"]
    histories = changelog["changelog"]["histories"]

    with _session() as db:
        counts = JiraAnalyticsCounts()
        issue = upsert_issue_payload(db, raw, worklogs=worklogs, histories=histories, counts=counts)
        assert issue is not None
        upsert_issue_payload(
            db, raw, worklogs=worklogs, histories=histories, counts=JiraAnalyticsCounts()
        )
        db.commit()

        assert db.scalar(select(JiraIssue).where(JiraIssue.key == "HUB-533")) is not None
        assert (
            db.scalar(select(JiraWorklog).where(JiraWorklog.jira_worklog_id == "85033")) is not None
        )
        assert db.scalar(select(func.count()).select_from(JiraWorklog)) == 1


def test_feature_membership_traverses_resolved_relations() -> None:
    with _session() as db:
        project = JiraProject(jira_project_id="100", key="PMGT", name="PMGT")
        db.add(project)
        db.flush()
        root = JiraIssue(
            jira_issue_id="1",
            key="PMGT-1",
            project_id=project.id,
            issue_type_name="Idea",
            summary="Root feature",
            last_seen_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
        )
        child = JiraIssue(
            jira_issue_id="2",
            key="HUB-1",
            issue_type_name="New Feature",
            summary="Implementation",
            last_seen_at=root.last_seen_at,
        )
        subtask = JiraIssue(
            jira_issue_id="3",
            key="HUB-2",
            issue_type_name="Development Subtask",
            summary="Subtask",
            last_seen_at=root.last_seen_at,
        )
        db.add_all([root, child, subtask])
        db.flush()
        db.add_all(
            [
                JiraIssueRelation(
                    source_issue_id=root.id,
                    target_issue_id=child.id,
                    target_key=child.key,
                    relation_source="issue_link",
                    link_type_name="implements",
                    direction="outward",
                    is_hierarchy_edge=False,
                    is_feature_membership_edge=True,
                ),
                JiraIssueRelation(
                    source_issue_id=child.id,
                    target_issue_id=subtask.id,
                    target_key=subtask.key,
                    relation_source="subtask",
                    link_type_name="Subtask",
                    direction="outward",
                    is_hierarchy_edge=True,
                    is_feature_membership_edge=True,
                ),
            ]
        )
        db.commit()

        counts = refresh_feature_memberships(db, root_issue_types=("Idea",), max_depth=5)
        assert counts.roots_upserted == 1
        assert counts.memberships_written == 3
        root_row = db.scalar(select(JiraFeatureRoot).where(JiraFeatureRoot.root_key == "PMGT-1"))
        assert root_row is not None
        memberships = (
            db.execute(
                select(JiraFeatureMembership).where(
                    JiraFeatureMembership.feature_root_id == root_row.id
                )
            )
            .scalars()
            .all()
        )
        assert {row.member_issue_id for row in memberships} == {root.id, child.id, subtask.id}


def test_feature_risk_uses_production_worklog_span_for_duration() -> None:
    with _session() as db:
        project = JiraProject(jira_project_id="100", key="PMGT", name="PMGT")
        db.add(project)
        db.flush()
        root = JiraIssue(
            jira_issue_id="1",
            key="PMGT-1",
            project_id=project.id,
            issue_type_name="Idea",
            summary="Risky open feature",
            status_name="Development",
            created_at_jira=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_seen_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
        )
        db.add(root)
        db.flush()
        child = JiraIssue(
            jira_issue_id="2",
            key="PMGT-2",
            project_id=project.id,
            issue_type_name="Story",
            summary="Implementation story",
            status_name="Done",
            status_category_key="done",
            parent_issue_id=root.id,
            parent_key=root.key,
            created_at_jira=datetime(2026, 1, 15, tzinfo=timezone.utc),
            last_seen_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
        )
        subtask = JiraIssue(
            jira_issue_id="3",
            key="PMGT-3",
            project_id=project.id,
            issue_type_name="Sub-task",
            summary="Implementation subtask",
            status_name="Development",
            status_category_key="indeterminate",
            parent_key=child.key,
            created_at_jira=datetime(2026, 1, 16, tzinfo=timezone.utc),
            last_seen_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
        )
        db.add_all([child, subtask])
        db.flush()
        feature_root = JiraFeatureRoot(
            root_issue_id=root.id,
            root_key=root.key,
            root_project_key="PMGT",
            root_issue_type_name="Idea",
            name="Risky open feature",
            detection_rule="unit_test",
        )
        db.add(feature_root)
        db.flush()
        db.add_all(
            [
                JiraIssueDetail(issue_id=root.id, team_name="Cosmic Coders"),
                JiraFeatureMembership(
                    feature_root_id=feature_root.id,
                    member_issue_id=root.id,
                    depth=0,
                    path_issue_keys=[root.key],
                    inclusion_reason="unit_test",
                ),
                JiraFeatureMembership(
                    feature_root_id=feature_root.id,
                    member_issue_id=child.id,
                    depth=1,
                    path_issue_keys=[root.key, child.key],
                    inclusion_reason="unit_test",
                ),
                JiraFeatureMembership(
                    feature_root_id=feature_root.id,
                    member_issue_id=subtask.id,
                    depth=2,
                    path_issue_keys=[root.key, child.key, subtask.key],
                    inclusion_reason="unit_test",
                ),
                JiraWorklog(
                    issue_id=root.id,
                    jira_worklog_id="wl-first",
                    author_account_id="dev",
                    author_display_name="Dev User",
                    started_at=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
                    time_spent_seconds=3600,
                ),
                JiraWorklog(
                    issue_id=root.id,
                    jira_worklog_id="wl-last",
                    author_account_id="dev",
                    author_display_name="Dev User",
                    started_at=datetime(2026, 5, 11, 17, 0, tzinfo=timezone.utc),
                    time_spent_seconds=3600,
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 5, 1),
                    topic_type="feature",
                    feature_key=root.key,
                    feature_name="Risky open feature",
                    issue_id=root.id,
                    issue_key=root.key,
                    team_name="Cosmic Coders",
                    source_user_email="dev@example.com",
                    source_display_name="Dev User",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=20,
                    rule_snapshot_json={},
                ),
            ]
        )
        db.commit()

        row = feature_risk(db).table[0]

        assert row["feature_title"] == "Risky open feature"
        assert row["status"] == "Development"
        assert "duration_days" not in row
        assert "duration_basis" not in row
        assert row["production_duration_days"] == 10
        assert row["lifecycle_duration_days"] is not None
        assert "lifecycle_duration_basis" not in row
        assert row["idle_before_work_days"] == 120
        assert row["size_risk_points"] == 2.0
        assert row["duration_risk_points"] == 2.0
        assert row["member_issue_count"] == 3
        assert row["child_issue_count"] == 2
        assert row["done_member_issue_count"] == 1
        assert row["open_member_issue_count"] == 2
        assert row["max_hierarchy_depth"] == 2
        assert row["structure_signal"] == "some_decomposition"
        assert row["risk_drivers"] == ["idle_before_start"]
        assert row["risk_score"] == 4.0


def test_feature_risk_without_worklogs_keeps_duration_unknown_and_status_visible() -> None:
    with _session() as db:
        project = JiraProject(jira_project_id="100", key="PMGT", name="PMGT")
        db.add(project)
        db.flush()
        root = JiraIssue(
            jira_issue_id="1",
            key="PMGT-1",
            project_id=project.id,
            issue_type_name="Idea",
            summary="Prepared feature",
            status_name="Backlog",
            created_at_jira=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_seen_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
        )
        db.add(root)
        db.flush()
        db.add_all(
            [
                JiraFeatureRoot(
                    root_issue_id=root.id,
                    root_key=root.key,
                    root_project_key="PMGT",
                    root_issue_type_name="Idea",
                    name="Prepared feature",
                    detection_rule="unit_test",
                ),
                JiraIssueDetail(issue_id=root.id, team_name="Cosmic Coders"),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 5, 1),
                    topic_type="feature",
                    feature_key=root.key,
                    feature_name="Prepared feature",
                    issue_id=root.id,
                    issue_key=root.key,
                    team_name="Cosmic Coders",
                    source_user_email="dev@example.com",
                    source_display_name="Dev User",
                    source_role_name="Developer",
                    allocation_kind="indirect_allocated",
                    hours=20,
                    rule_snapshot_json={},
                ),
            ]
        )
        db.commit()

        row = feature_risk(db).table[0]

        assert row["feature_title"] == "Prepared feature"
        assert row["status"] == "Backlog"
        assert "duration_days" not in row
        assert "duration_basis" not in row
        assert row["production_duration_days"] is None
        assert row["lifecycle_duration_days"] is not None
        assert row["structure_signal"] == "unknown_structure"
        assert row["risk_drivers"] == ["missing_production_duration"]
        assert row["risk_score"] == 2.0


def test_size_vs_speed_adds_production_duration_and_hours_per_day_kpis() -> None:
    with _session() as db:
        project = JiraProject(jira_project_id="100", key="PMGT", name="PMGT")
        db.add(project)
        db.flush()
        root = JiraIssue(
            jira_issue_id="size-speed-root",
            key="PMGT-99",
            project_id=project.id,
            issue_type_name="Idea",
            summary="Sized feature",
            status_name="Development",
            created_at_jira=datetime(2026, 1, 1, tzinfo=timezone.utc),
            resolved_at_jira=datetime(2026, 5, 21, tzinfo=timezone.utc),
            last_seen_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
        )
        db.add(root)
        db.flush()
        feature_root = JiraFeatureRoot(
            root_issue_id=root.id,
            root_key=root.key,
            root_project_key="PMGT",
            root_issue_type_name="Idea",
            name="Sized feature",
            detection_rule="unit_test",
        )
        db.add(feature_root)
        db.flush()
        db.add_all(
            [
                JiraIssueDetail(
                    issue_id=root.id,
                    team_name="Cosmic Coders",
                    actual_end=datetime(2026, 5, 21, tzinfo=timezone.utc),
                ),
                JiraFeatureMembership(
                    feature_root_id=feature_root.id,
                    member_issue_id=root.id,
                    depth=0,
                    path_issue_keys=[root.key],
                    inclusion_reason="unit_test",
                ),
                JiraWorklog(
                    issue_id=root.id,
                    jira_worklog_id="wl-first",
                    author_account_id="dev",
                    author_display_name="Dev User",
                    started_at=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
                    time_spent_seconds=3600,
                ),
                JiraWorklog(
                    issue_id=root.id,
                    jira_worklog_id="wl-last",
                    author_account_id="dev",
                    author_display_name="Dev User",
                    started_at=datetime(2026, 5, 11, 17, 0, tzinfo=timezone.utc),
                    time_spent_seconds=3600,
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 5, 1),
                    topic_type="feature",
                    feature_key=root.key,
                    feature_name="Sized feature",
                    issue_id=root.id,
                    issue_key=root.key,
                    team_name="Cosmic Coders",
                    source_user_email="dev@example.com",
                    source_display_name="Dev User",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=40,
                    rule_snapshot_json={},
                ),
            ]
        )
        db.commit()

        row = size_vs_speed(db).table[0]

        assert row["feature_key"] == "PMGT-99"
        assert row["feature_name"] == "Sized feature"
        assert row["hours"] == 40
        assert row["production_duration_days"] == 10
        assert row["hours_per_production_day"] == 4.0
        assert row["lifecycle_days"] == 140
        assert row["duration_days"] == 140
        assert row["hours_per_lifecycle_day"] == round(40 / 140, 2)


def test_size_vs_speed_without_worklogs_keeps_production_kpis_null() -> None:
    with _session() as db:
        project = JiraProject(jira_project_id="100", key="PMGT", name="PMGT")
        db.add(project)
        db.flush()
        root = JiraIssue(
            jira_issue_id="size-speed-prepared",
            key="PMGT-100",
            project_id=project.id,
            issue_type_name="Idea",
            summary="Prepared feature",
            status_name="Backlog",
            created_at_jira=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_seen_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
        )
        db.add(root)
        db.flush()
        db.add_all(
            [
                JiraFeatureRoot(
                    root_issue_id=root.id,
                    root_key=root.key,
                    root_project_key="PMGT",
                    root_issue_type_name="Idea",
                    name="Prepared feature",
                    detection_rule="unit_test",
                ),
                JiraIssueDetail(issue_id=root.id, team_name="Cosmic Coders"),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 5, 1),
                    topic_type="feature",
                    feature_key=root.key,
                    feature_name="Prepared feature",
                    issue_id=root.id,
                    issue_key=root.key,
                    team_name="Cosmic Coders",
                    source_user_email="dev@example.com",
                    source_display_name="Dev User",
                    source_role_name="Developer",
                    allocation_kind="indirect_allocated",
                    hours=20,
                    rule_snapshot_json={},
                ),
            ]
        )
        db.commit()

        row = size_vs_speed(db).table[0]

        assert row["feature_name"] == "Prepared feature"
        assert row["hours"] == 20
        assert row["lifecycle_days"] is None
        assert row["duration_days"] is None
        assert row["production_duration_days"] is None
        assert row["hours_per_production_day"] is None
        assert row["hours_per_lifecycle_day"] is None


def test_investment_by_theme_groups_by_pmgt_product() -> None:
    with _session() as db:
        project = JiraProject(jira_project_id="100", key="PMGT", name="PMGT")
        db.add(project)
        db.flush()
        root = JiraIssue(
            jira_issue_id="theme-root",
            key="PMGT-77",
            project_id=project.id,
            issue_type_name="Idea",
            summary="Theme feature",
            last_seen_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
        )
        child = JiraIssue(
            jira_issue_id="theme-child",
            key="HUB-77",
            project_id=project.id,
            issue_type_name="Improvement",
            summary="Theme child",
            last_seen_at=root.last_seen_at,
        )
        db.add_all([root, child])
        db.flush()
        feature_root = JiraFeatureRoot(
            root_issue_id=root.id,
            root_key=root.key,
            root_project_key="PMGT",
            root_issue_type_name="Idea",
            name=root.summary,
            detection_rule="unit_test",
        )
        db.add(feature_root)
        db.flush()
        db.add_all(
            [
                JiraIssueDetail(
                    issue_id=root.id,
                    epic_thema="Legacy Theme",
                    pmgt_product=[
                        {"value": "Strategic"},
                        {"value": "Retention"},
                    ],
                ),
                JiraIssueDetail(issue_id=child.id, epic_thema="Wrong Child Theme"),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 5, 1),
                    topic_type="feature",
                    feature_root_id=feature_root.id,
                    feature_key=root.key,
                    feature_name=root.summary,
                    issue_id=child.id,
                    issue_key=child.key,
                    source_user_email="dev@example.com",
                    source_display_name="Dev User",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=10,
                    rule_snapshot_json={},
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2027, 1, 1),
                    topic_type="feature",
                    feature_root_id=feature_root.id,
                    feature_key=root.key,
                    feature_name=root.summary,
                    issue_id=child.id,
                    issue_key=child.key,
                    source_user_email="dev@example.com",
                    source_display_name="Dev User",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=4,
                    rule_snapshot_json={},
                ),
            ]
        )
        db.commit()

        payload = investment_by_theme(
            db,
            date_from=date(2026, 5, 1),
            date_to=date(2027, 1, 1),
        )

        assert payload.table == [
            {"theme": "Retention", "hours": 7.0},
            {"theme": "Strategic", "hours": 7.0},
        ]
        assert payload.series == [
            {"period": "2026-05-01", "Retention": 5.0, "Strategic": 5.0},
            {"period": "2027-01-01", "Retention": 2.0, "Strategic": 2.0},
        ]
        assert payload.filters["yearly_series"] == [
            {"year": "2026", "Retention": 5.0, "Strategic": 5.0},
            {"year": "2027", "Retention": 2.0, "Strategic": 2.0},
        ]


def test_customer_effort_splits_hours_by_customer_and_topic() -> None:
    with _session() as db:
        project = JiraProject(jira_project_id="101", key="HUB", name="Hub")
        db.add(project)
        db.flush()
        issue = JiraIssue(
            jira_issue_id="cust-issue",
            key="HUB-101",
            project_id=project.id,
            issue_type_name="Bug",
            summary="Customer bug",
            last_seen_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
        )
        other_issue = JiraIssue(
            jira_issue_id="cust-other",
            key="HUB-102",
            project_id=project.id,
            issue_type_name="Improvement",
            summary="No customer",
            last_seen_at=issue.last_seen_at,
        )
        db.add_all([issue, other_issue])
        db.flush()
        db.add_all(
            [
                JiraIssueDetail(issue_id=issue.id, customers=["Volkswagen", "Siemens"]),
                JiraIssueDetail(issue_id=other_issue.id, customers=None),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 5, 1),
                    topic_type="unassigned_bug",
                    issue_id=issue.id,
                    issue_key=issue.key,
                    source_user_email="dev@example.com",
                    source_display_name="Dev User",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=10,
                    rule_snapshot_json={},
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 6, 1),
                    topic_type="feature",
                    issue_id=issue.id,
                    issue_key=issue.key,
                    source_user_email="dev@example.com",
                    source_display_name="Dev User",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=6,
                    rule_snapshot_json={},
                ),
                MonthlyAllocatedEffort(
                    period_month=date(2026, 6, 1),
                    topic_type="tech_support",
                    issue_id=other_issue.id,
                    issue_key=other_issue.key,
                    source_user_email="dev@example.com",
                    source_display_name="Dev User",
                    source_role_name="Developer",
                    allocation_kind="direct_worklog",
                    hours=4,
                    rule_snapshot_json={},
                ),
            ]
        )
        db.commit()

        payload = customer_effort(
            db,
            date_from=date(2026, 5, 1),
            date_to=date(2026, 6, 30),
        )

        assert payload.summary == {
            "customer_count": 2,
            "attributed_hours": 16.0,
            "unattributed_hours": 4.0,
        }
        assert payload.table == [
            {
                "customer": "Siemens",
                "feature_hours": 3.0,
                "bugfix_hours": 5.0,
                "support_hours": 0.0,
                "improvement_hours": 0.0,
                "other_hours": 0.0,
                "total_hours": 8.0,
            },
            {
                "customer": "Volkswagen",
                "feature_hours": 3.0,
                "bugfix_hours": 5.0,
                "support_hours": 0.0,
                "improvement_hours": 0.0,
                "other_hours": 0.0,
                "total_hours": 8.0,
            },
        ]
        assert payload.series == [
            {"period": "2026-05-01", "Siemens": 5.0, "Volkswagen": 5.0},
            {"period": "2026-06-01", "Siemens": 3.0, "Volkswagen": 3.0},
        ]
        assert payload.filters["attribution_method"] == "equal_split"
        assert payload.filters["available_customers"] == ["Siemens", "Volkswagen"]

        filtered = customer_effort(
            db,
            date_from=date(2026, 5, 1),
            date_to=date(2026, 6, 30),
            customer="Siemens",
        )
        assert len(filtered.table) == 1
        assert filtered.table[0]["customer"] == "Siemens"


def test_upsert_relations_allows_multiple_issue_links_to_same_target() -> None:
    raw = _fixture("sample_issue.json")
    raw["key"] = "BM-999"
    fields = raw["fields"]
    link_type = {
        "id": "10003",
        "name": "Relates",
        "inward": "relates to",
        "outward": "relates to",
    }
    fields["parent"] = None
    fields["subtasks"] = []
    fields["issuelinks"] = [
        {
            "id": "29163",
            "type": link_type,
            "inwardIssue": {"id": "1", "key": "EVENT-44"},
        },
        {
            "id": "29172",
            "type": link_type,
            "inwardIssue": {"id": "1", "key": "EVENT-44"},
        },
    ]

    with _session() as db:
        issue = upsert_issue_payload(db, raw, counts=JiraAnalyticsCounts())
        assert issue is not None
        db.commit()
        relates_links = (
            db.execute(
                select(JiraIssueRelation).where(
                    JiraIssueRelation.source_issue_id == issue.id,
                    JiraIssueRelation.relation_source == "issue_link",
                )
            )
            .scalars()
            .all()
        )
        assert len(relates_links) == 2
        assert {row.jira_link_id for row in relates_links} == {"29163", "29172"}
        upsert_issue_payload(db, raw, counts=JiraAnalyticsCounts())
        db.commit()
        relates_links_again = (
            db.execute(
                select(JiraIssueRelation).where(
                    JiraIssueRelation.source_issue_id == issue.id,
                    JiraIssueRelation.relation_source == "issue_link",
                )
            )
            .scalars()
            .all()
        )
        assert len(relates_links_again) == 2


def test_feature_membership_assigns_single_primary_pmgt_per_issue() -> None:
    with _session() as db:
        pmgt = JiraProject(jira_project_id="100", key="PMGT", name="PMGT")
        hub = JiraProject(jira_project_id="101", key="HUB", name="HUB")
        db.add_all([pmgt, hub])
        db.flush()
        now = datetime(2026, 5, 20, tzinfo=timezone.utc)
        pmgt_a = JiraIssue(
            jira_issue_id="1",
            key="PMGT-A",
            project_id=pmgt.id,
            issue_type_name="Idea",
            summary="Feature A",
            last_seen_at=now,
        )
        pmgt_b = JiraIssue(
            jira_issue_id="2",
            key="PMGT-B",
            project_id=pmgt.id,
            issue_type_name="Idea",
            summary="Feature B",
            last_seen_at=now,
        )
        epic = JiraIssue(
            jira_issue_id="3",
            key="HUB-1",
            project_id=hub.id,
            issue_type_name="Epic",
            summary="Shared epic",
            last_seen_at=now,
        )
        story = JiraIssue(
            jira_issue_id="4",
            key="HUB-2",
            project_id=hub.id,
            issue_type_name="Improvement",
            summary="Story",
            last_seen_at=now,
        )
        db.add_all([pmgt_a, pmgt_b, epic, story])
        db.flush()
        db.add(
            JiraIssueDetail(
                issue_id=story.id,
                epic_link_issue_id=epic.id,
                epic_link_key=epic.key,
            )
        )
        db.add_all(
            [
                JiraIssueRelation(
                    source_issue_id=pmgt_a.id,
                    target_issue_id=epic.id,
                    target_key=epic.key,
                    relation_source="connected_pmgt_issue",
                    link_type_name="implements",
                    direction="outward",
                    is_feature_membership_edge=True,
                ),
                JiraIssueRelation(
                    source_issue_id=pmgt_b.id,
                    target_issue_id=story.id,
                    target_key=story.key,
                    relation_source="connected_pmgt_issue",
                    link_type_name="implements",
                    direction="outward",
                    is_feature_membership_edge=True,
                ),
                JiraIssueRelation(
                    source_issue_id=story.id,
                    target_issue_id=epic.id,
                    target_key=epic.key,
                    relation_source="issue_link",
                    link_type_name="Blocks",
                    direction="outward",
                    is_feature_membership_edge=True,
                ),
            ]
        )
        db.commit()

        refresh_feature_memberships(db, root_issue_types=("Idea",), max_depth=8)
        memberships = db.execute(select(JiraFeatureMembership)).scalars().all()
        by_member = {row.member_issue_id: row for row in memberships}
        assert len(by_member) == len(memberships)
        assert by_member[story.id].feature_root_id == db.scalar(
            select(JiraFeatureRoot.id).where(JiraFeatureRoot.root_key == "PMGT-B")
        )


def test_feature_membership_prefers_pmgt_project_over_idea() -> None:
    with _session() as db:
        pmgt = JiraProject(jira_project_id="100", key="PMGT", name="PMGT")
        hub = JiraProject(jira_project_id="101", key="HUB", name="HUB")
        db.add_all([pmgt, hub])
        db.flush()
        now = datetime(2026, 5, 20, tzinfo=timezone.utc)
        idea = JiraIssue(
            jira_issue_id="1",
            key="PMGT-IDEA",
            project_id=pmgt.id,
            issue_type_name="Idea",
            summary="Idea root",
            last_seen_at=now,
        )
        project = JiraIssue(
            jira_issue_id="2",
            key="PMGT-PROJECT",
            project_id=pmgt.id,
            issue_type_name="Project",
            summary="Project root",
            last_seen_at=now,
        )
        issue = JiraIssue(
            jira_issue_id="3",
            key="HUB-2",
            project_id=hub.id,
            issue_type_name="Improvement",
            summary="Implementation",
            last_seen_at=now,
        )
        db.add_all([idea, project, issue])
        db.flush()
        db.add_all(
            [
                JiraIssueRelation(
                    source_issue_id=issue.id,
                    target_issue_id=idea.id,
                    target_key=idea.key,
                    relation_source="connected_pmgt_issue",
                    link_type_name="Polaris work item link",
                    direction="outward",
                    is_feature_membership_edge=True,
                ),
                JiraIssueRelation(
                    source_issue_id=issue.id,
                    target_issue_id=project.id,
                    target_key=project.key,
                    relation_source="connected_pmgt_issue",
                    link_type_name="Polaris work item link",
                    direction="outward",
                    is_feature_membership_edge=True,
                ),
            ]
        )
        db.commit()

        refresh_feature_memberships(db)
        membership = db.scalar(
            select(JiraFeatureMembership).where(JiraFeatureMembership.member_issue_id == issue.id)
        )
        assert membership is not None
        assert membership.feature_root_id == db.scalar(
            select(JiraFeatureRoot.id).where(JiraFeatureRoot.root_key == "PMGT-PROJECT")
        )


def test_feature_membership_ignores_archived_pmgt_root() -> None:
    with _session() as db:
        pmgt = JiraProject(jira_project_id="100", key="PMGT", name="PMGT")
        hub = JiraProject(jira_project_id="101", key="HUB", name="HUB")
        db.add_all([pmgt, hub])
        db.flush()
        now = datetime(2026, 5, 20, tzinfo=timezone.utc)
        archived_project = JiraIssue(
            jira_issue_id="1",
            key="PMGT-ARCHIVED",
            project_id=pmgt.id,
            issue_type_name="Project",
            summary="Archived project",
            last_seen_at=now,
            raw_fields_json={"customfield_10251": True},
        )
        active_idea = JiraIssue(
            jira_issue_id="2",
            key="PMGT-ACTIVE",
            project_id=pmgt.id,
            issue_type_name="Idea",
            summary="Active idea",
            last_seen_at=now,
            raw_fields_json={"customfield_10251": False},
        )
        issue = JiraIssue(
            jira_issue_id="3",
            key="HUB-3",
            project_id=hub.id,
            issue_type_name="Improvement",
            summary="Implementation",
            last_seen_at=now,
        )
        db.add_all([archived_project, active_idea, issue])
        db.flush()
        db.add_all(
            [
                JiraIssueRelation(
                    source_issue_id=issue.id,
                    target_issue_id=archived_project.id,
                    target_key=archived_project.key,
                    relation_source="connected_pmgt_issue",
                    link_type_name="Polaris work item link",
                    direction="outward",
                    is_feature_membership_edge=True,
                ),
                JiraIssueRelation(
                    source_issue_id=issue.id,
                    target_issue_id=active_idea.id,
                    target_key=active_idea.key,
                    relation_source="connected_pmgt_issue",
                    link_type_name="Polaris work item link",
                    direction="outward",
                    is_feature_membership_edge=True,
                ),
            ]
        )
        db.commit()

        refresh_feature_memberships(db)
        membership = db.scalar(
            select(JiraFeatureMembership).where(JiraFeatureMembership.member_issue_id == issue.id)
        )
        assert membership is not None
        assert membership.feature_root_id == db.scalar(
            select(JiraFeatureRoot.id).where(JiraFeatureRoot.root_key == "PMGT-ACTIVE")
        )


def test_feature_membership_project_root_reaches_epic_children() -> None:
    with _session() as db:
        pmgt = JiraProject(jira_project_id="100", key="PMGT", name="PMGT")
        rest = JiraProject(jira_project_id="101", key="REST", name="REST")
        bm = JiraProject(jira_project_id="102", key="BM", name="BM")
        db.add_all([pmgt, rest, bm])
        db.flush()
        now = datetime(2026, 5, 20, tzinfo=timezone.utc)
        root = JiraIssue(
            jira_issue_id="1",
            key="PMGT-119",
            project_id=pmgt.id,
            issue_type_name="Project",
            summary="IntegrationJob",
            last_seen_at=now,
        )
        epic = JiraIssue(
            jira_issue_id="2",
            key="BM-33206",
            project_id=bm.id,
            issue_type_name="Epic",
            summary="IntegrationJob epic",
            last_seen_at=now,
        )
        child = JiraIssue(
            jira_issue_id="3",
            key="REST-731",
            project_id=rest.id,
            issue_type_name="New Feature",
            summary="Changes after review",
            parent_issue_id=epic.id,
            last_seen_at=now,
        )
        db.add_all([root, epic, child])
        db.flush()
        db.add(
            JiraIssueDetail(issue_id=child.id, epic_link_issue_id=epic.id, epic_link_key=epic.key)
        )
        db.add_all(
            [
                JiraIssueRelation(
                    source_issue_id=epic.id,
                    target_issue_id=root.id,
                    target_key=root.key,
                    relation_source="connected_pmgt_issue",
                    link_type_name="Polaris work item link",
                    direction="outward",
                    is_feature_membership_edge=True,
                ),
                JiraIssueRelation(
                    source_issue_id=child.id,
                    target_issue_id=epic.id,
                    target_key=epic.key,
                    relation_source="parent",
                    link_type_name="Parent",
                    direction="outward",
                    is_hierarchy_edge=True,
                    is_feature_membership_edge=True,
                ),
                JiraIssueRelation(
                    source_issue_id=child.id,
                    target_issue_id=epic.id,
                    target_key=epic.key,
                    relation_source="epic_link",
                    link_type_name="Epic Link",
                    direction="outward",
                    is_hierarchy_edge=True,
                    is_feature_membership_edge=True,
                ),
            ]
        )
        db.commit()

        refresh_feature_memberships(db)
        membership = db.scalar(
            select(JiraFeatureMembership).where(JiraFeatureMembership.member_issue_id == child.id)
        )
        assert membership is not None
        assert membership.feature_root_id == db.scalar(
            select(JiraFeatureRoot.id).where(JiraFeatureRoot.root_key == "PMGT-119")
        )
        assert membership.path_issue_keys == ["PMGT-119", "BM-33206", "REST-731"]


def test_feature_membership_reaches_epic_story_and_subtask_chain() -> None:
    """PMGT root -> linked epic -> story (epic link) -> dev subtask (parent)."""
    with _session() as db:
        pmgt_project = JiraProject(jira_project_id="100", key="PMGT", name="PMGT")
        iau_project = JiraProject(jira_project_id="200", key="IAU", name="IAU")
        db.add_all([pmgt_project, iau_project])
        db.flush()

        pmgt_root = JiraIssue(
            jira_issue_id="1",
            key="PMGT-12",
            project_id=pmgt_project.id,
            issue_type_name="Idea",
            summary="Feature root",
            last_seen_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
        )
        epic = JiraIssue(
            jira_issue_id="2",
            key="IAU-122",
            project_id=iau_project.id,
            issue_type_name="Epic",
            summary="Implementation epic",
            last_seen_at=pmgt_root.last_seen_at,
        )
        story = JiraIssue(
            jira_issue_id="3",
            key="IAU-161",
            project_id=iau_project.id,
            issue_type_name="Improvement",
            summary="Story",
            last_seen_at=pmgt_root.last_seen_at,
        )
        subtask = JiraIssue(
            jira_issue_id="4",
            key="IAU-173",
            project_id=iau_project.id,
            issue_type_name="Development Subtask",
            summary="Dev subtask",
            parent_issue_id=None,
            last_seen_at=pmgt_root.last_seen_at,
        )
        db.add_all([pmgt_root, epic, story, subtask])
        db.flush()
        story.parent_issue_id = None
        subtask.parent_issue_id = story.id
        db.add(
            JiraIssueDetail(
                issue_id=story.id,
                epic_link_issue_id=epic.id,
                epic_link_key=epic.key,
            )
        )
        db.add(
            JiraIssueRelation(
                source_issue_id=epic.id,
                target_issue_id=pmgt_root.id,
                target_key=pmgt_root.key,
                relation_source="connected_pmgt_issue",
                link_type_name="implements",
                direction="outward",
                is_hierarchy_edge=True,
                is_feature_membership_edge=True,
            )
        )
        db.commit()

        counts = refresh_feature_memberships(db, root_issue_types=("Idea",), max_depth=8)
        assert counts.roots_upserted == 1
        root_row = db.scalar(select(JiraFeatureRoot).where(JiraFeatureRoot.root_key == "PMGT-12"))
        assert root_row is not None
        member_keys = {
            db.get(JiraIssue, row.member_issue_id).key
            for row in db.execute(
                select(JiraFeatureMembership).where(
                    JiraFeatureMembership.feature_root_id == root_row.id
                )
            ).scalars()
        }
        assert member_keys == {"PMGT-12", "IAU-122", "IAU-161", "IAU-173"}


def test_adf_to_text_handles_plain_text_nodes() -> None:
    assert adf_to_text({"type": "doc", "content": [{"type": "text", "text": "Hello"}]}) == "Hello"
