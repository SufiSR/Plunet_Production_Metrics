"""Split jira_issue_relation uniqueness by jira_link_id vs hierarchy edges.

Revision ID: 20260522_0010
Revises: 20260520_0009
Create Date: 2026-05-22

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260522_0010"
down_revision = "20260520_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_jira_issue_relation_direct_identity",
        "jira_issue_relation",
        type_="unique",
    )
    # Remove historical duplicates before partial unique indexes are applied.
    op.execute(
        sa.text(
            """
            DELETE FROM jira_issue_relation AS older
            USING jira_issue_relation AS newer
            WHERE older.id < newer.id
              AND older.source_issue_id = newer.source_issue_id
              AND older.jira_link_id IS NOT NULL
              AND older.jira_link_id = newer.jira_link_id
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM jira_issue_relation AS older
            USING jira_issue_relation AS newer
            WHERE older.id < newer.id
              AND older.jira_link_id IS NULL
              AND newer.jira_link_id IS NULL
              AND older.source_issue_id = newer.source_issue_id
              AND older.target_key IS NOT DISTINCT FROM newer.target_key
              AND older.relation_source = newer.relation_source
              AND older.link_type_name = newer.link_type_name
              AND older.direction = newer.direction
            """
        )
    )
    op.create_index(
        "uq_jira_issue_relation_jira_link_id",
        "jira_issue_relation",
        ["source_issue_id", "jira_link_id"],
        unique=True,
        postgresql_where=sa.text("jira_link_id IS NOT NULL"),
        sqlite_where=sa.text("jira_link_id IS NOT NULL"),
    )
    op.create_index(
        "uq_jira_issue_relation_direct_identity",
        "jira_issue_relation",
        ["source_issue_id", "target_key", "relation_source", "link_type_name", "direction"],
        unique=True,
        postgresql_where=sa.text("jira_link_id IS NULL"),
        sqlite_where=sa.text("jira_link_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_jira_issue_relation_direct_identity",
        table_name="jira_issue_relation",
        postgresql_where=sa.text("jira_link_id IS NULL"),
        sqlite_where=sa.text("jira_link_id IS NULL"),
    )
    op.drop_index(
        "uq_jira_issue_relation_jira_link_id",
        table_name="jira_issue_relation",
        postgresql_where=sa.text("jira_link_id IS NOT NULL"),
        sqlite_where=sa.text("jira_link_id IS NOT NULL"),
    )
    op.create_unique_constraint(
        "uq_jira_issue_relation_direct_identity",
        "jira_issue_relation",
        ["source_issue_id", "target_key", "relation_source", "link_type_name", "direction"],
    )
