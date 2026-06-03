"""hrworks person roster cache

Revision ID: 20260523_0012
Revises: 20260523_0011
Create Date: 2026-05-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260523_0012"
down_revision = "20260523_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hrworks_person_roster",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("person_id", sa.String(length=255), nullable=False),
        sa.Column("hrworks_uuid", sa.String(length=64), nullable=True),
        sa.Column("personnel_number", sa.String(length=64), nullable=True),
        sa.Column("business_email", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("join_date", sa.Date(), nullable=True),
        sa.Column("leave_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("jira_user_id", sa.BigInteger(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["jira_user_id"],
            ["jira_user.id"],
            name=op.f("fk_hrworks_person_roster_jira_user_id_jira_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hrworks_person_roster")),
        sa.UniqueConstraint("person_id", name="uq_hrworks_person_roster_person_id"),
    )
    op.create_index(
        "ix_hrworks_person_roster_jira_user_id",
        "hrworks_person_roster",
        ["jira_user_id"],
    )
    op.create_index(
        "ix_hrworks_person_roster_leave_date",
        "hrworks_person_roster",
        ["leave_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_hrworks_person_roster_leave_date", table_name="hrworks_person_roster")
    op.drop_index("ix_hrworks_person_roster_jira_user_id", table_name="hrworks_person_roster")
    op.drop_table("hrworks_person_roster")
