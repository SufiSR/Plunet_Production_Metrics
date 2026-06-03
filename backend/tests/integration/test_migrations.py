from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration

# Core tables that must exist after Alembic upgrade head (all domain models)
_EXPECTED_TABLES = frozenset(
    {
        "alembic_version",
        "app_configuration",
        "repository",
        "merge_request",
        "release",
        "sync_log",
        "metric_snapshot",
        "production_bug",
        "bug_release",
        "issue_worklog",
        "jira_project",
        "jira_user",
        "jira_issue",
        "jira_issue_detail",
        "jira_issue_field_value",
        "jira_worklog",
        "jira_issue_status_transition",
        "jira_sprint",
        "jira_issue_sprint",
        "jira_issue_relation",
        "jira_feature_root",
        "jira_feature_membership",
        "jira_feature_family",
        "jira_feature_family_member",
        "jira_feature_family_suggestion_decision",
        "jira_user_monthly_hrworks_hours",
        "hrworks_person_roster",
        "allocation_role_rule",
        "jira_user_role_assignment",
        "monthly_topic_effort_base",
        "monthly_allocated_effort",
        "workflow_status_classification",
        "jira_workflow",
        "jira_project_workflow_mapping",
    }
)


def test_db_connection_and_schema_after_migration(migrated_database_url: str) -> None:
    engine = create_engine(migrated_database_url)
    with engine.connect() as connection:
        one = connection.execute(text("SELECT 1")).scalar_one()
        assert one == 1

        version = connection.execute(
            text("SELECT version_num FROM alembic_version LIMIT 1")
        ).scalar_one()
        assert isinstance(version, str) and version.strip() != ""

        rows = connection.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )
        ).fetchall()
        present = {r[0] for r in rows}
        assert _EXPECTED_TABLES.issubset(present), (
            f"Missing tables: {sorted(_EXPECTED_TABLES - present)}"
        )
