"""merge_request: jira_ready_for_qa_at for non-bug Jira issues on MRs

Revision ID: 20260401_0004
Revises: 20260401_0003
Create Date: 2026-04-01
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260401_0004"
down_revision = "20260401_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "merge_request",
        sa.Column("jira_ready_for_qa_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("merge_request", "jira_ready_for_qa_at")
