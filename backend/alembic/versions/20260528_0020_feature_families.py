"""add managed feature families

Revision ID: 20260528_0020
Revises: 20260528_0019
Create Date: 2026-05-28
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260528_0020"
down_revision = "20260528_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jira_feature_family",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("suggestion_keywords", sa.JSON(), nullable=True),
        sa.Column("title_match_pattern", sa.String(length=512), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jira_feature_family")),
        sa.UniqueConstraint("name", name="uq_jira_feature_family_name"),
    )
    op.create_index("ix_jira_feature_family_active", "jira_feature_family", ["active"])

    op.create_table(
        "jira_feature_family_member",
        sa.Column("family_id", sa.BigInteger(), nullable=False),
        sa.Column("feature_root_id", sa.BigInteger(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["family_id"], ["jira_feature_family.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["feature_root_id"], ["jira_feature_root.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint(
            "family_id", "feature_root_id", name=op.f("pk_jira_feature_family_member")
        ),
        sa.UniqueConstraint(
            "feature_root_id", name="uq_jira_feature_family_member_feature_root"
        ),
    )
    op.create_index(
        "ix_jira_feature_family_member_family",
        "jira_feature_family_member",
        ["family_id"],
    )

    op.create_table(
        "jira_feature_family_suggestion_decision",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("family_id", sa.BigInteger(), nullable=False),
        sa.Column("feature_root_id", sa.BigInteger(), nullable=False),
        sa.Column("suggestion_fingerprint", sa.String(length=255), nullable=False),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.String(length=1024), nullable=True),
        sa.Column("decided_by", sa.String(length=255), nullable=True),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["family_id"], ["jira_feature_family.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["feature_root_id"], ["jira_feature_root.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint(
            "id", name=op.f("pk_jira_feature_family_suggestion_decision")
        ),
        sa.UniqueConstraint(
            "family_id",
            "feature_root_id",
            "suggestion_fingerprint",
            name="uq_jira_feature_family_suggestion_decision",
        ),
    )
    op.create_index(
        "ix_jira_feature_family_suggestion_decision_family",
        "jira_feature_family_suggestion_decision",
        ["family_id"],
    )
    op.create_index(
        "ix_jira_feature_family_suggestion_decision_feature",
        "jira_feature_family_suggestion_decision",
        ["feature_root_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_jira_feature_family_suggestion_decision_feature",
        table_name="jira_feature_family_suggestion_decision",
    )
    op.drop_index(
        "ix_jira_feature_family_suggestion_decision_family",
        table_name="jira_feature_family_suggestion_decision",
    )
    op.drop_table("jira_feature_family_suggestion_decision")
    op.drop_index("ix_jira_feature_family_member_family", table_name="jira_feature_family_member")
    op.drop_table("jira_feature_family_member")
    op.drop_index("ix_jira_feature_family_active", table_name="jira_feature_family")
    op.drop_table("jira_feature_family")
