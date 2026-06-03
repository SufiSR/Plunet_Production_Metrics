"""add solutions engineer allocation role

Revision ID: 20260528_0019
Revises: 20260527_0018
Create Date: 2026-05-28
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260528_0019"
down_revision = "20260527_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            """
            INSERT INTO allocation_role_rule (
                role_name, is_direct_production_role, is_indirect_role,
                overhead_percentage, allocation_scope, allocation_base, active
            )
            VALUES (
                'Solutions Engineer', true, false,
                0, 'direct_issue', 'direct_production_hours', true
            )
            ON CONFLICT (role_name) DO UPDATE SET
                is_direct_production_role = EXCLUDED.is_direct_production_role,
                is_indirect_role = EXCLUDED.is_indirect_role,
                overhead_percentage = EXCLUDED.overhead_percentage,
                allocation_scope = EXCLUDED.allocation_scope,
                allocation_base = EXCLUDED.allocation_base,
                active = true
            """
        )
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM allocation_role_rule WHERE role_name = 'Solutions Engineer'")
    )
