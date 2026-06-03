"""jira workflow definitions and project mappings

Revision ID: 20260527_0018
Revises: 20260526_0017
Create Date: 2026-05-27
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260527_0018"
down_revision = "20260526_0017"
branch_labels = None
depends_on = None

DEFAULT_ISSUE_TYPE_KEY = "__default__"


def upgrade() -> None:
    op.create_table(
        "jira_workflow",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("jira_entity_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status_order_json", sa.JSON(), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jira_workflow")),
        sa.UniqueConstraint("jira_entity_id", name="uq_jira_workflow_jira_entity_id"),
        sa.UniqueConstraint("name", name="uq_jira_workflow_name"),
    )

    op.create_table(
        "jira_project_workflow_mapping",
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("issue_type_id", sa.String(length=64), nullable=False),
        sa.Column("workflow_id", sa.BigInteger(), nullable=False),
        sa.Column("issue_type_name", sa.String(length=100), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["jira_project.id"],
            name=op.f("fk_jira_project_workflow_mapping_project_id_jira_project"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["jira_workflow.id"],
            name=op.f("fk_jira_project_workflow_mapping_workflow_id_jira_workflow"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "project_id",
            "issue_type_id",
            name=op.f("pk_jira_project_workflow_mapping"),
        ),
    )
    op.create_index(
        "ix_jira_project_workflow_mapping_workflow_id",
        "jira_project_workflow_mapping",
        ["workflow_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_jira_project_workflow_mapping_workflow_id",
        table_name="jira_project_workflow_mapping",
    )
    op.drop_table("jira_project_workflow_mapping")
    op.drop_table("jira_workflow")
