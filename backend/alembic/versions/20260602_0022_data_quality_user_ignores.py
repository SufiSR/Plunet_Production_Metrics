"""add user-level data quality ignores

Revision ID: 20260602_0022
Revises: 20260529_0021
Create Date: 2026-06-02
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260602_0022"
down_revision = "20260529_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jira_data_quality_user_ignore",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("check_id", sa.String(length=100), nullable=False),
        sa.Column("jira_user_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["jira_user_id"], ["jira_user.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("check_id", "jira_user_id", name="uq_jira_data_quality_user_ignore_check_user"),
    )
    op.create_index(
        "ix_jira_data_quality_user_ignore_check_active",
        "jira_data_quality_user_ignore",
        ["check_id", "active"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_jira_data_quality_user_ignore_check_active",
        table_name="jira_data_quality_user_ignore",
    )
    op.drop_table("jira_data_quality_user_ignore")
