"""issue_worklog jira_account_id

Revision ID: 20260505_0008
Revises: 20260417_0007
Create Date: 2026-05-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260505_0008"
down_revision = "20260417_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "issue_worklog",
        sa.Column("jira_account_id", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_issue_worklog_jira_account_id",
        "issue_worklog",
        ["jira_account_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_issue_worklog_jira_account_id", table_name="issue_worklog")
    op.drop_column("issue_worklog", "jira_account_id")
