"""assignment roles and remove worklog denylist

Revision ID: 20260526_0015
Revises: 20260526_0014
Create Date: 2026-05-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260526_0015"
down_revision = "20260526_0014"
branch_labels = None
depends_on = None

_RULES = [
    ("Support Agent", True, False, 0, "direct_issue", "direct_production_hours"),
    ("Head of Dev", False, True, 30, "global", "direct_production_hours"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for role_name, direct, indirect, overhead, scope, base in _RULES:
        conn.execute(
            sa.text(
                """
                INSERT INTO allocation_role_rule (
                    role_name, is_direct_production_role, is_indirect_role,
                    overhead_percentage, allocation_scope, allocation_base, active
                )
                VALUES (
                    :role_name, :direct, :indirect, :overhead, :scope, :base, true
                )
                ON CONFLICT (role_name) DO UPDATE SET
                    is_direct_production_role = EXCLUDED.is_direct_production_role,
                    is_indirect_role = EXCLUDED.is_indirect_role,
                    overhead_percentage = EXCLUDED.overhead_percentage,
                    allocation_scope = EXCLUDED.allocation_scope,
                    allocation_base = EXCLUDED.allocation_base,
                    active = true
                """
            ),
            {
                "role_name": role_name,
                "direct": direct,
                "indirect": indirect,
                "overhead": overhead,
                "scope": scope,
                "base": base,
            },
        )
    conn.execute(
        sa.text(
            "UPDATE jira_user_role_assignment SET role_name = 'Support Agent' WHERE role_name = 'Tech Support'"
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE app_configuration
            SET settings_json = jsonb_set(
                COALESCE(settings_json::jsonb, '{}'::jsonb),
                '{jira}',
                (COALESCE(settings_json::jsonb -> 'jira', '{}'::jsonb) - 'jira_worklog_author_denylist'),
                true
            )::json
            WHERE settings_json IS NOT NULL
              AND settings_json::jsonb ? 'jira'
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE jira_user_role_assignment SET role_name = 'Tech Support' WHERE role_name = 'Support Agent'"
        )
    )
    conn.execute(
        sa.text("DELETE FROM allocation_role_rule WHERE role_name IN ('Support Agent', 'Head of Dev')")
    )
