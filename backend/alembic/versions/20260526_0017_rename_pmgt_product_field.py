"""rename PMGT Product field storage

Revision ID: 20260526_0017
Revises: 20260526_0016
Create Date: 2026-05-26
"""

from __future__ import annotations

from alembic import op

revision = "20260526_0017"
down_revision = "20260526_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("jira_issue_detail", "pmgt_customfield_10286", new_column_name="pmgt_product")


def downgrade() -> None:
    op.alter_column("jira_issue_detail", "pmgt_product", new_column_name="pmgt_customfield_10286")
