"""rename merge_request inserted_at to updated_at

Revision ID: 20260401_0002
Revises: 20260331_0001
Create Date: 2026-04-01 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260401_0002"
down_revision = "20260331_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = {c["name"] for c in inspector.get_columns("merge_request")}
    if "inserted_at" in cols and "updated_at" not in cols:
        op.execute('ALTER TABLE merge_request RENAME COLUMN inserted_at TO updated_at')


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = {c["name"] for c in inspector.get_columns("merge_request")}
    if "updated_at" in cols and "inserted_at" not in cols:
        op.execute('ALTER TABLE merge_request RENAME COLUMN updated_at TO inserted_at')
