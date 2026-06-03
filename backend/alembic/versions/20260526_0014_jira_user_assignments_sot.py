"""jira user assignments source of truth

Revision ID: 20260526_0014
Revises: 20260523_0013
Create Date: 2026-05-26
"""

from __future__ import annotations

import json
from datetime import date

import sqlalchemy as sa
from alembic import op

revision = "20260526_0014"
down_revision = "20260523_0013"
branch_labels = None
depends_on = None

_WORKLOG_TO_ALLOCATION = {
    "dev": "Developer",
    "qa": "QA",
    "pm": "Product Manager",
    "sup": "Support Agent",
}


def _import_settings_assignments(connection) -> None:
    row = connection.execute(
        sa.text("SELECT settings_json FROM app_configuration WHERE id = 1")
    ).fetchone()
    if not row or not row[0]:
        return
    settings = row[0]
    if isinstance(settings, str):
        settings = json.loads(settings)
    if not isinstance(settings, dict):
        return
    jira = settings.get("jira")
    if not isinstance(jira, dict):
        return
    raw = jira.get("jira_worklog_user_assignments")
    if not isinstance(raw, list) or not raw:
        return

    today = date.today()
    for item in raw:
        if not isinstance(item, dict):
            continue
        account_id = str(item.get("jira_account_id") or "").strip() or None
        author = str(item.get("author") or "").strip() or None
        role_key = str(item.get("role") or "").strip().lower()
        team = str(item.get("team") or "").strip() or None
        role_name = _WORKLOG_TO_ALLOCATION.get(role_key)
        if not role_name:
            continue
        if not account_id and not author:
            continue

        user_id = None
        display = author or account_id or "Unknown"
        email = ""
        if account_id:
            user_row = connection.execute(
                sa.text("SELECT id, display_name, email_address FROM jira_user WHERE account_id = :aid"),
                {"aid": account_id},
            ).fetchone()
            if user_row:
                user_id, display, email = user_row[0], user_row[1] or display, user_row[2] or ""
            else:
                connection.execute(
                    sa.text(
                        "INSERT INTO jira_user (account_id, display_name, email_address, reporting_excluded) "
                        "VALUES (:aid, :dn, :em, false)"
                    ),
                    {
                        "aid": account_id,
                        "dn": display,
                        "em": f"{account_id}@unknown.local",
                    },
                )
                user_id = connection.execute(
                    sa.text("SELECT id FROM jira_user WHERE account_id = :aid"),
                    {"aid": account_id},
                ).scalar_one()
                email = f"{account_id}@unknown.local"
        elif author:
            email = f"{author.lower().replace(' ', '.')}@unknown.local"

        if user_id is None and account_id:
            user_id = connection.execute(
                sa.text("SELECT id FROM jira_user WHERE account_id = :aid"),
                {"aid": account_id},
            ).scalar_one_or_none()

        connection.execute(
            sa.text(
                """
                INSERT INTO jira_user_role_assignment (
                    jira_user_id, user_account_id, user_email, display_name,
                    role_name, team_id, team_name, valid_from, valid_to, active
                )
                VALUES (
                    :jira_user_id, :user_account_id, :user_email, :display_name,
                    :role_name, :team_id, :team_name, :valid_from, NULL, true
                )
                """
            ),
            {
                "jira_user_id": user_id,
                "user_account_id": account_id,
                "user_email": email or f"{display}@unknown.local",
                "display_name": display,
                "role_name": role_name,
                "team_id": team,
                "team_name": team,
                "valid_from": today,
            },
        )


def upgrade() -> None:
    op.add_column(
        "jira_user",
        sa.Column(
            "reporting_excluded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "jira_user_role_assignment",
        sa.Column("jira_user_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "jira_user_role_assignment",
        sa.Column("allocatable_percentage", sa.Numeric(precision=5, scale=2), nullable=True),
    )
    op.add_column(
        "jira_user_role_assignment",
        sa.Column("allocation_scope", sa.String(length=50), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_jira_user_role_assignment_jira_user_id_jira_user"),
        "jira_user_role_assignment",
        "jira_user",
        ["jira_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_jira_user_role_assignment_jira_user_valid",
        "jira_user_role_assignment",
        ["jira_user_id", "valid_from"],
    )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE jira_user_role_assignment ura
            SET jira_user_id = u.id
            FROM jira_user u
            WHERE ura.user_account_id IS NOT NULL
              AND ura.user_account_id = u.account_id
              AND ura.jira_user_id IS NULL
            """
        )
    )

    existing = connection.execute(
        sa.text("SELECT COUNT(*) FROM jira_user_role_assignment")
    ).scalar_one()
    if int(existing or 0) == 0:
        _import_settings_assignments(connection)
    else:
        connection.execute(
            sa.text(
                """
                UPDATE jira_user_role_assignment ura
                SET jira_user_id = u.id
                FROM jira_user u
                WHERE ura.jira_user_id IS NULL
                  AND ura.user_account_id IS NOT NULL
                  AND ura.user_account_id = u.account_id
                """
            )
        )


def downgrade() -> None:
    op.drop_index("ix_jira_user_role_assignment_jira_user_valid", table_name="jira_user_role_assignment")
    op.drop_constraint(
        op.f("fk_jira_user_role_assignment_jira_user_id_jira_user"),
        "jira_user_role_assignment",
        type_="foreignkey",
    )
    op.drop_column("jira_user_role_assignment", "allocation_scope")
    op.drop_column("jira_user_role_assignment", "allocatable_percentage")
    op.drop_column("jira_user_role_assignment", "jira_user_id")
    op.drop_column("jira_user", "reporting_excluded")
