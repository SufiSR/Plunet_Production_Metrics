"""jira user monthly hrworks hours

Revision ID: 20260523_0011
Revises: 20260522_0010
Create Date: 2026-05-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260523_0011"
down_revision = "20260522_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jira_user_monthly_hrworks_hours",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("jira_user_id", sa.BigInteger(), nullable=False),
        sa.Column("month_start", sa.Date(), nullable=False),
        sa.Column("month_end", sa.Date(), nullable=False),
        sa.Column("planned_working_hours", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("clocked_working_hours", sa.Numeric(precision=10, scale=2), nullable=False),
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
            name=op.f("fk_jira_user_monthly_hrworks_hours_jira_user_id_jira_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jira_user_monthly_hrworks_hours")),
        sa.UniqueConstraint(
            "jira_user_id",
            "month_start",
            name="uq_jira_user_monthly_hrworks_hours_user_month",
        ),
    )
    op.create_index(
        "ix_jira_user_monthly_hrworks_hours_month_start",
        "jira_user_monthly_hrworks_hours",
        ["month_start"],
    )
    op.create_index(
        "ix_jira_user_monthly_hrworks_hours_user_month",
        "jira_user_monthly_hrworks_hours",
        ["jira_user_id", "month_start"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_jira_user_monthly_hrworks_hours_user_month",
        table_name="jira_user_monthly_hrworks_hours",
    )
    op.drop_index(
        "ix_jira_user_monthly_hrworks_hours_month_start",
        table_name="jira_user_monthly_hrworks_hours",
    )
    op.drop_table("jira_user_monthly_hrworks_hours")
