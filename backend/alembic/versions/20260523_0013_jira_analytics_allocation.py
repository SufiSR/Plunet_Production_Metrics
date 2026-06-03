"""jira analytics allocation and reporting tables

Revision ID: 20260523_0013
Revises: 20260523_0012
Create Date: 2026-05-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260523_0013"
down_revision = "20260523_0012"
branch_labels = None
depends_on = None

_SEED_RULES = [
    ("Developer", True, False, 0, "direct_issue", "direct_production_hours"),
    ("QA", True, False, 0, "direct_issue", "direct_production_hours"),
    ("UX Research", True, False, 0, "direct_issue", "direct_production_hours"),
    ("UX Design", True, False, 0, "direct_issue", "direct_production_hours"),
    ("Product Owner", False, True, 20, "team_only", "direct_production_hours"),
    ("Product Manager", False, True, 30, "global", "direct_production_hours"),
    ("System Architect", False, True, 30, "global", "direct_production_hours"),
    ("Support Agent", True, False, 0, "direct_issue", "direct_production_hours"),
    ("Head of Dev", False, True, 30, "global", "direct_production_hours"),
]


def upgrade() -> None:
    op.create_table(
        "allocation_role_rule",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("role_name", sa.String(length=100), nullable=False),
        sa.Column("is_direct_production_role", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_indirect_role", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("overhead_percentage", sa.Numeric(precision=5, scale=2), nullable=False, server_default="0"),
        sa.Column("allocation_scope", sa.String(length=50), nullable=False),
        sa.Column("allocation_base", sa.String(length=50), nullable=False, server_default="direct_production_hours"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_allocation_role_rule")),
        sa.UniqueConstraint("role_name", name="uq_allocation_role_rule_role_name"),
    )

    op.create_table(
        "jira_user_role_assignment",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_account_id", sa.String(length=128), nullable=True),
        sa.Column("user_email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("role_name", sa.String(length=100), nullable=False),
        sa.Column("team_id", sa.String(length=128), nullable=True),
        sa.Column("team_name", sa.String(length=255), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jira_user_role_assignment")),
    )
    op.create_index(
        "ix_jira_user_role_assignment_account_valid",
        "jira_user_role_assignment",
        ["user_account_id", "valid_from"],
    )

    op.create_table(
        "monthly_topic_effort_base",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("period_month", sa.Date(), nullable=False),
        sa.Column("feature_root_id", sa.BigInteger(), nullable=True),
        sa.Column("feature_key", sa.String(length=50), nullable=True),
        sa.Column("feature_name", sa.String(length=1024), nullable=True),
        sa.Column("issue_id", sa.BigInteger(), nullable=False),
        sa.Column("issue_key", sa.String(length=50), nullable=False),
        sa.Column("issue_type_name", sa.String(length=100), nullable=True),
        sa.Column("summary", sa.String(length=1024), nullable=True),
        sa.Column("team_id", sa.String(length=128), nullable=True),
        sa.Column("team_name", sa.String(length=255), nullable=True),
        sa.Column("user_account_id", sa.String(length=128), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("role_name", sa.String(length=100), nullable=True),
        sa.Column("topic_type", sa.String(length=50), nullable=False),
        sa.Column("direct_hours", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column(
            "refreshed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["feature_root_id"],
            ["jira_feature_root.id"],
            name=op.f("fk_monthly_topic_effort_base_feature_root_id_jira_feature_root"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["issue_id"],
            ["jira_issue.id"],
            name=op.f("fk_monthly_topic_effort_base_issue_id_jira_issue"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_monthly_topic_effort_base")),
    )
    op.create_index(
        "ix_monthly_topic_effort_base_period_topic",
        "monthly_topic_effort_base",
        ["period_month", "topic_type"],
    )
    op.create_index(
        "ix_monthly_topic_effort_base_period_feature",
        "monthly_topic_effort_base",
        ["period_month", "feature_root_id"],
    )

    op.create_table(
        "monthly_allocated_effort",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("period_month", sa.Date(), nullable=False),
        sa.Column("topic_type", sa.String(length=50), nullable=False),
        sa.Column("feature_root_id", sa.BigInteger(), nullable=True),
        sa.Column("feature_key", sa.String(length=50), nullable=True),
        sa.Column("feature_name", sa.String(length=1024), nullable=True),
        sa.Column("issue_id", sa.BigInteger(), nullable=True),
        sa.Column("issue_key", sa.String(length=50), nullable=True),
        sa.Column("team_id", sa.String(length=128), nullable=True),
        sa.Column("team_name", sa.String(length=255), nullable=True),
        sa.Column("source_user_email", sa.String(length=255), nullable=False),
        sa.Column("source_display_name", sa.String(length=255), nullable=False),
        sa.Column("source_role_name", sa.String(length=100), nullable=False),
        sa.Column("allocation_kind", sa.String(length=50), nullable=False),
        sa.Column("hours", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("allocation_basis_hours", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("allocation_percentage", sa.Numeric(precision=12, scale=8), nullable=True),
        sa.Column("rule_snapshot_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["feature_root_id"],
            ["jira_feature_root.id"],
            name=op.f("fk_monthly_allocated_effort_feature_root_id_jira_feature_root"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["issue_id"],
            ["jira_issue.id"],
            name=op.f("fk_monthly_allocated_effort_issue_id_jira_issue"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_monthly_allocated_effort")),
    )
    op.create_index(
        "ix_monthly_allocated_effort_period_kind",
        "monthly_allocated_effort",
        ["period_month", "allocation_kind"],
    )
    op.create_index(
        "ix_monthly_allocated_effort_period_feature",
        "monthly_allocated_effort",
        ["period_month", "feature_root_id"],
    )

    op.create_table(
        "workflow_status_classification",
        sa.Column("status_name", sa.String(length=100), primary_key=True),
        sa.Column("status_class", sa.String(length=50), nullable=False),
    )

    rules = sa.table(
        "allocation_role_rule",
        sa.column("role_name", sa.String),
        sa.column("is_direct_production_role", sa.Boolean),
        sa.column("is_indirect_role", sa.Boolean),
        sa.column("overhead_percentage", sa.Numeric),
        sa.column("allocation_scope", sa.String),
        sa.column("allocation_base", sa.String),
        sa.column("active", sa.Boolean),
    )
    op.bulk_insert(
        rules,
        [
            {
                "role_name": name,
                "is_direct_production_role": direct,
                "is_indirect_role": indirect,
                "overhead_percentage": overhead,
                "allocation_scope": scope,
                "allocation_base": base,
                "active": True,
            }
            for name, direct, indirect, overhead, scope, base in _SEED_RULES
        ],
    )


def downgrade() -> None:
    op.drop_table("workflow_status_classification")
    op.drop_index("ix_monthly_allocated_effort_period_feature", table_name="monthly_allocated_effort")
    op.drop_index("ix_monthly_allocated_effort_period_kind", table_name="monthly_allocated_effort")
    op.drop_table("monthly_allocated_effort")
    op.drop_index("ix_monthly_topic_effort_base_period_feature", table_name="monthly_topic_effort_base")
    op.drop_index("ix_monthly_topic_effort_base_period_topic", table_name="monthly_topic_effort_base")
    op.drop_table("monthly_topic_effort_base")
    op.drop_index("ix_jira_user_role_assignment_account_valid", table_name="jira_user_role_assignment")
    op.drop_table("jira_user_role_assignment")
    op.drop_table("allocation_role_rule")
