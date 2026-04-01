"""bug_release: add ON DELETE CASCADE to foreign keys

Revision ID: 20260401_0005
Revises: 20260401_0004
Create Date: 2026-04-01
"""

from __future__ import annotations

from alembic import op

revision = "20260401_0005"
down_revision = "20260401_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "bug_release_bug_id_fkey", "bug_release", type_="foreignkey",
    )
    op.drop_constraint(
        "bug_release_release_id_fkey", "bug_release", type_="foreignkey",
    )
    op.create_foreign_key(
        "bug_release_bug_id_fkey", "bug_release",
        "production_bug", ["bug_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "bug_release_release_id_fkey", "bug_release",
        "release", ["release_id"], ["id"], ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "bug_release_release_id_fkey", "bug_release", type_="foreignkey",
    )
    op.drop_constraint(
        "bug_release_bug_id_fkey", "bug_release", type_="foreignkey",
    )
    op.create_foreign_key(
        "bug_release_bug_id_fkey", "bug_release",
        "production_bug", ["bug_id"], ["id"],
    )
    op.create_foreign_key(
        "bug_release_release_id_fkey", "bug_release",
        "release", ["release_id"], ["id"],
    )
