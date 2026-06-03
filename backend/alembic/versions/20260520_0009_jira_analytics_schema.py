"""jira analytics schema

Revision ID: 20260520_0009
Revises: 20260505_0008
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260520_0009"
down_revision = "20260505_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jira_project",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("jira_project_id", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("category_name", sa.String(length=255), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jira_project")),
        sa.UniqueConstraint("jira_project_id", name="uq_jira_project_jira_project_id"),
        sa.UniqueConstraint("key", name="uq_jira_project_key"),
    )
    op.create_index("ix_jira_project_category_name", "jira_project", ["category_name"])

    op.create_table(
        "jira_user",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("email_address", sa.String(length=255), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("time_zone", sa.String(length=100), nullable=True),
        sa.Column("account_type", sa.String(length=50), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jira_user")),
        sa.UniqueConstraint("account_id", name="uq_jira_user_account_id"),
    )

    op.create_table(
        "jira_issue",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("jira_issue_id", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("self_url", sa.Text(), nullable=True),
        sa.Column("project_id", sa.BigInteger(), nullable=True),
        sa.Column("issue_type_id", sa.String(length=64), nullable=True),
        sa.Column("issue_type_name", sa.String(length=100), nullable=True),
        sa.Column("issue_type_hierarchy_level", sa.Integer(), nullable=True),
        sa.Column("summary", sa.String(length=1024), nullable=True),
        sa.Column("description_text", sa.Text(), nullable=True),
        sa.Column("description_adf", sa.JSON(), nullable=True),
        sa.Column("status_id", sa.String(length=64), nullable=True),
        sa.Column("status_name", sa.String(length=100), nullable=True),
        sa.Column("status_category_key", sa.String(length=64), nullable=True),
        sa.Column("status_category_name", sa.String(length=100), nullable=True),
        sa.Column("resolution_id", sa.String(length=64), nullable=True),
        sa.Column("resolution_name", sa.String(length=100), nullable=True),
        sa.Column("priority_id", sa.String(length=64), nullable=True),
        sa.Column("priority_name", sa.String(length=100), nullable=True),
        sa.Column("assignee_user_id", sa.BigInteger(), nullable=True),
        sa.Column("creator_user_id", sa.BigInteger(), nullable=True),
        sa.Column("reporter_user_id", sa.BigInteger(), nullable=True),
        sa.Column("parent_issue_id", sa.BigInteger(), nullable=True),
        sa.Column("parent_jira_issue_id", sa.String(length=64), nullable=True),
        sa.Column("parent_key", sa.String(length=50), nullable=True),
        sa.Column("created_at_jira", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at_jira", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at_jira", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_fields_json", sa.JSON(), nullable=True),
        sa.Column("raw_issue_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["assignee_user_id"], ["jira_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["creator_user_id"], ["jira_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_issue_id"], ["jira_issue.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["jira_project.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["jira_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jira_issue")),
        sa.UniqueConstraint("jira_issue_id", name="uq_jira_issue_jira_issue_id"),
        sa.UniqueConstraint("key", name="uq_jira_issue_key"),
    )
    op.create_index("ix_jira_issue_created_at_jira", "jira_issue", ["created_at_jira"])
    op.create_index("ix_jira_issue_parent_issue_id", "jira_issue", ["parent_issue_id"])
    op.create_index(
        "ix_jira_issue_project_issue_type", "jira_issue", ["project_id", "issue_type_name"]
    )
    op.create_index("ix_jira_issue_resolved_at_jira", "jira_issue", ["resolved_at_jira"])
    op.create_index(
        "ix_jira_issue_status_updated", "jira_issue", ["status_name", "updated_at_jira"]
    )

    op.create_table(
        "jira_issue_detail",
        sa.Column("issue_id", sa.BigInteger(), nullable=False),
        sa.Column("promised_delivery_date", sa.Date(), nullable=True),
        sa.Column("customer_transparency", sa.String(length=255), nullable=True),
        sa.Column("external_issue_url", sa.Text(), nullable=True),
        sa.Column("to_be_verified_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("solution", sa.Text(), nullable=True),
        sa.Column("promised_sold_on", sa.Date(), nullable=True),
        sa.Column("target_branches", sa.JSON(), nullable=True),
        sa.Column("documentation", sa.JSON(), nullable=True),
        sa.Column("version_value", sa.String(length=255), nullable=True),
        sa.Column("epic_thema", sa.String(length=255), nullable=True),
        sa.Column("maintainer_user_id", sa.BigInteger(), nullable=True),
        sa.Column("design", sa.Text(), nullable=True),
        sa.Column("goals", sa.Text(), nullable=True),
        sa.Column("delivery_status", sa.String(length=255), nullable=True),
        sa.Column("external_issue_id", sa.String(length=255), nullable=True),
        sa.Column("epic_link_key", sa.String(length=50), nullable=True),
        sa.Column("epic_link_issue_id", sa.BigInteger(), nullable=True),
        sa.Column("ux_required", sa.String(length=50), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("change_type", sa.String(length=255), nullable=True),
        sa.Column("change_risk", sa.String(length=255), nullable=True),
        sa.Column("change_reason", sa.String(length=255), nullable=True),
        sa.Column("actual_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("customer_priority", sa.String(length=255), nullable=True),
        sa.Column("actual_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("team_id", sa.String(length=128), nullable=True),
        sa.Column("team_name", sa.String(length=255), nullable=True),
        sa.Column("customers", sa.JSON(), nullable=True),
        sa.Column("labels", sa.JSON(), nullable=True),
        sa.Column("components", sa.JSON(), nullable=True),
        sa.Column("affects_versions", sa.JSON(), nullable=True),
        sa.Column("fix_versions", sa.JSON(), nullable=True),
        sa.Column("raw_required_fields_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["epic_link_issue_id"], ["jira_issue.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["issue_id"], ["jira_issue.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["maintainer_user_id"], ["jira_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["to_be_verified_by_user_id"], ["jira_user.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("issue_id", name=op.f("pk_jira_issue_detail")),
    )
    op.create_index(
        "ix_jira_issue_detail_delivery_status", "jira_issue_detail", ["delivery_status"]
    )
    op.create_index("ix_jira_issue_detail_epic_link_key", "jira_issue_detail", ["epic_link_key"])
    op.create_index(
        "ix_jira_issue_detail_promised_delivery_date",
        "jira_issue_detail",
        ["promised_delivery_date"],
    )
    op.create_index(
        "ix_jira_issue_detail_promised_sold_on", "jira_issue_detail", ["promised_sold_on"]
    )
    op.create_index("ix_jira_issue_detail_team_name", "jira_issue_detail", ["team_name"])

    op.create_table(
        "jira_issue_field_value",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("issue_id", sa.BigInteger(), nullable=False),
        sa.Column("field_id", sa.String(length=100), nullable=False),
        sa.Column("field_name", sa.String(length=255), nullable=True),
        sa.Column("schema_type", sa.String(length=100), nullable=True),
        sa.Column("schema_custom", sa.String(length=255), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_number", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("value_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["issue_id"], ["jira_issue.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jira_issue_field_value")),
        sa.UniqueConstraint("issue_id", "field_id", name="uq_jira_issue_field_value_issue_field"),
    )
    op.create_index(
        "ix_jira_issue_field_value_field_date", "jira_issue_field_value", ["field_id", "value_date"]
    )
    op.create_index(
        "ix_jira_issue_field_value_field_text", "jira_issue_field_value", ["field_id", "value_text"]
    )

    op.create_table(
        "jira_sprint",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("jira_sprint_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("state", sa.String(length=50), nullable=True),
        sa.Column("board_id", sa.BigInteger(), nullable=True),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("complete_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jira_sprint")),
        sa.UniqueConstraint("jira_sprint_id", name="uq_jira_sprint_jira_sprint_id"),
    )

    op.create_table(
        "jira_worklog",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("issue_id", sa.BigInteger(), nullable=False),
        sa.Column("jira_worklog_id", sa.String(length=64), nullable=False),
        sa.Column("author_user_id", sa.BigInteger(), nullable=True),
        sa.Column("author_account_id", sa.String(length=128), nullable=True),
        sa.Column("author_display_name", sa.String(length=255), nullable=True),
        sa.Column("author_email_address", sa.String(length=255), nullable=True),
        sa.Column("comment_text", sa.Text(), nullable=True),
        sa.Column("comment_adf", sa.JSON(), nullable=True),
        sa.Column("created_at_jira", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at_jira", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_spent_seconds", sa.Integer(), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["author_user_id"], ["jira_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["issue_id"], ["jira_issue.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jira_worklog")),
        sa.UniqueConstraint("issue_id", "jira_worklog_id", name="uq_jira_worklog_issue_worklog"),
    )
    op.create_index(
        "ix_jira_worklog_author_started", "jira_worklog", ["author_user_id", "started_at"]
    )
    op.create_index("ix_jira_worklog_issue_started", "jira_worklog", ["issue_id", "started_at"])
    op.create_index("ix_jira_worklog_started_at", "jira_worklog", ["started_at"])

    op.create_table(
        "jira_issue_status_transition",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("issue_id", sa.BigInteger(), nullable=False),
        sa.Column("jira_history_id", sa.String(length=64), nullable=False),
        sa.Column("history_item_index", sa.Integer(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("changed_by_display_name", sa.String(length=255), nullable=True),
        sa.Column("from_status_id", sa.String(length=64), nullable=True),
        sa.Column("from_status_name", sa.String(length=100), nullable=True),
        sa.Column("to_status_id", sa.String(length=64), nullable=True),
        sa.Column("to_status_name", sa.String(length=100), nullable=True),
        sa.Column("raw_item_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["jira_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["issue_id"], ["jira_issue.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jira_issue_status_transition")),
        sa.UniqueConstraint(
            "issue_id",
            "jira_history_id",
            "history_item_index",
            name="uq_jira_issue_status_transition_history_item",
        ),
    )
    op.create_index(
        "ix_jira_issue_status_transition_issue_changed",
        "jira_issue_status_transition",
        ["issue_id", "changed_at"],
    )
    op.create_index(
        "ix_jira_issue_status_transition_to_status_changed",
        "jira_issue_status_transition",
        ["to_status_name", "changed_at"],
    )

    op.create_table(
        "jira_issue_sprint",
        sa.Column("issue_id", sa.BigInteger(), nullable=False),
        sa.Column("sprint_id", sa.BigInteger(), nullable=False),
        sa.Column("source_field_id", sa.String(length=100), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["issue_id"], ["jira_issue.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sprint_id"], ["jira_sprint.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("issue_id", "sprint_id", name=op.f("pk_jira_issue_sprint")),
    )

    op.create_table(
        "jira_issue_relation",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_issue_id", sa.BigInteger(), nullable=False),
        sa.Column("target_issue_id", sa.BigInteger(), nullable=True),
        sa.Column("target_jira_issue_id", sa.String(length=64), nullable=True),
        sa.Column("target_key", sa.String(length=50), nullable=True),
        sa.Column("relation_source", sa.String(length=50), nullable=False),
        sa.Column("jira_link_id", sa.String(length=64), nullable=True),
        sa.Column("link_type_id", sa.String(length=64), nullable=True),
        sa.Column("link_type_name", sa.String(length=100), nullable=False),
        sa.Column("direction", sa.String(length=30), nullable=False),
        sa.Column("inward_description", sa.String(length=255), nullable=True),
        sa.Column("outward_description", sa.String(length=255), nullable=True),
        sa.Column("is_hierarchy_edge", sa.Boolean(), nullable=False),
        sa.Column("is_feature_membership_edge", sa.Boolean(), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_issue_id"], ["jira_issue.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_issue_id"], ["jira_issue.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jira_issue_relation")),
        sa.UniqueConstraint(
            "source_issue_id",
            "target_key",
            "relation_source",
            "link_type_name",
            "direction",
            name="uq_jira_issue_relation_direct_identity",
        ),
    )
    op.create_index(
        "ix_jira_issue_relation_feature_membership",
        "jira_issue_relation",
        ["is_feature_membership_edge"],
    )
    op.create_index(
        "ix_jira_issue_relation_source_issue_id", "jira_issue_relation", ["source_issue_id"]
    )
    op.create_index(
        "ix_jira_issue_relation_source_type",
        "jira_issue_relation",
        ["relation_source", "link_type_name"],
    )
    op.create_index(
        "ix_jira_issue_relation_target_issue_id", "jira_issue_relation", ["target_issue_id"]
    )
    op.create_index("ix_jira_issue_relation_target_key", "jira_issue_relation", ["target_key"])

    op.create_table(
        "jira_feature_root",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("root_issue_id", sa.BigInteger(), nullable=False),
        sa.Column("root_key", sa.String(length=50), nullable=False),
        sa.Column("root_project_key", sa.String(length=50), nullable=False),
        sa.Column("root_issue_type_name", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=1024), nullable=True),
        sa.Column("detection_rule", sa.String(length=100), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["root_issue_id"], ["jira_issue.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jira_feature_root")),
        sa.UniqueConstraint("root_issue_id", name="uq_jira_feature_root_root_issue_id"),
    )
    op.create_index("ix_jira_feature_root_active", "jira_feature_root", ["active"])
    op.create_index(
        "ix_jira_feature_root_project_type",
        "jira_feature_root",
        ["root_project_key", "root_issue_type_name"],
    )

    op.create_table(
        "jira_feature_membership",
        sa.Column("feature_root_id", sa.BigInteger(), nullable=False),
        sa.Column("member_issue_id", sa.BigInteger(), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column("path_issue_keys", sa.JSON(), nullable=False),
        sa.Column("path_relation_ids", sa.JSON(), nullable=True),
        sa.Column("inclusion_reason", sa.String(length=100), nullable=False),
        sa.Column("nearest_parent_issue_id", sa.BigInteger(), nullable=True),
        sa.Column("direct_relation_id", sa.BigInteger(), nullable=True),
        sa.Column("contains_cycle", sa.Boolean(), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["direct_relation_id"], ["jira_issue_relation.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["feature_root_id"], ["jira_feature_root.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_issue_id"], ["jira_issue.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["nearest_parent_issue_id"], ["jira_issue.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint(
            "feature_root_id", "member_issue_id", name=op.f("pk_jira_feature_membership")
        ),
    )
    op.create_index(
        "ix_jira_feature_membership_member_issue_id", "jira_feature_membership", ["member_issue_id"]
    )
    op.create_index(
        "ix_jira_feature_membership_root_depth",
        "jira_feature_membership",
        ["feature_root_id", "depth"],
    )


def downgrade() -> None:
    for table in (
        "jira_feature_membership",
        "jira_feature_root",
        "jira_issue_relation",
        "jira_issue_sprint",
        "jira_issue_status_transition",
        "jira_worklog",
        "jira_sprint",
        "jira_issue_field_value",
        "jira_issue_detail",
        "jira_issue",
        "jira_user",
        "jira_project",
    ):
        op.drop_table(table)
