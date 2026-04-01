"""production_bug: nullable created_at, jira_created_at_valid flag

Revision ID: 20260401_0003
Revises: 20260401_0002
Create Date: 2026-04-01
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260401_0003"
down_revision = "20260401_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "production_bug",
        sa.Column(
            "jira_created_at_valid",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.alter_column(
        "production_bug", "created_at",
        existing_type=sa.DateTime(timezone=True), nullable=True,
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE production_bug SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP) "
            "WHERE created_at IS NULL"
        )
    )
    op.alter_column(
        "production_bug", "created_at",
        existing_type=sa.DateTime(timezone=True), nullable=False,
    )
    op.drop_column("production_bug", "jira_created_at_valid")
