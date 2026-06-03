"""rename FreeGuys team label to FreeDevs across analytics tables

Revision ID: 20260529_0021
Revises: 20260528_0020
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260529_0021"
down_revision = "20260528_0020"
branch_labels = None
depends_on = None

_TEAM_TABLES = (
    "jira_user_role_assignment",
    "jira_issue_detail",
    "monthly_allocated_effort",
    "monthly_topic_effort_base",
)


def _rename_team(bind: sa.engine.Connection, *, old_name: str, new_name: str) -> None:
    for table in _TEAM_TABLES:
        bind.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET team_name = :new_name
                WHERE team_name = :old_name
                """
            ),
            {"old_name": old_name, "new_name": new_name},
        )
        bind.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET team_id = :new_name
                WHERE team_id = :old_name
                """
            ),
            {"old_name": old_name, "new_name": new_name},
        )


def upgrade() -> None:
    _rename_team(op.get_bind(), old_name="FreeGuys", new_name="FreeDevs")


def downgrade() -> None:
    bind = op.get_bind()
    # Only revert rows introduced as FreeGuys (valid_from on/after 2026-05-27) so older
    # FreeDevs assignment history is not rewritten.
    bind.execute(
        sa.text(
            """
            UPDATE jira_user_role_assignment
            SET team_name = 'FreeGuys', team_id = 'FreeGuys'
            WHERE team_name = 'FreeDevs'
              AND team_id = 'FreeDevs'
              AND valid_from >= DATE '2026-05-27'
            """
        )
    )
    for table in ("jira_issue_detail", "monthly_allocated_effort", "monthly_topic_effort_base"):
        bind.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET team_name = 'FreeGuys', team_id = 'FreeGuys'
                WHERE team_name = 'FreeDevs' AND team_id = 'FreeDevs'
                """
            )
        )
