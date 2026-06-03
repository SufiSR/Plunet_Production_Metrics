"""store PMGT customfield 10286

Revision ID: 20260526_0016
Revises: 20260526_0015
Create Date: 2026-05-26
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260526_0016"
down_revision = "20260526_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jira_issue_detail",
        sa.Column("pmgt_customfield_10286", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jira_issue_detail", "pmgt_customfield_10286")
