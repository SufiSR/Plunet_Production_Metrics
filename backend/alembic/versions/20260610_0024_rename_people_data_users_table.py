"""rename people data users table to plural

Revision ID: 20260610_0024
Revises: 20260610_0023
Create Date: 2026-06-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260610_0024"
down_revision = "20260610_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "people_data_user" in tables and "people_data_users" not in tables:
        op.rename_table("people_data_user", "people_data_users")


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "people_data_users" in tables and "people_data_user" not in tables:
        op.rename_table("people_data_users", "people_data_user")
