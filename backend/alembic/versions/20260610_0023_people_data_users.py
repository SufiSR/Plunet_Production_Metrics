"""add people data users

Revision ID: 20260610_0023
Revises: 20260602_0022
Create Date: 2026-06-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260610_0023"
down_revision = "20260602_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "people_data_users",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("username_normalized", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "username_normalized",
            name="uq_people_data_users_username_normalized",
        ),
    )


def downgrade() -> None:
    op.drop_table("people_data_users")
