"""metric_snapshot lead time diagnostics columns

Revision ID: 20260417_0007
Revises: 20260402_0006
Create Date: 2026-04-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260417_0007"
down_revision = "20260402_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "metric_snapshot",
        sa.Column("lead_time_sample_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "metric_snapshot",
        sa.Column("lead_time_match_counts", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("metric_snapshot", "lead_time_match_counts")
    op.drop_column("metric_snapshot", "lead_time_sample_count")
