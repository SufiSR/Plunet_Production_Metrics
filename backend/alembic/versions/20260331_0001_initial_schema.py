"""initial schema

Revision ID: 20260331_0001
Revises:
Create Date: 2026-03-31 13:35:00
"""
# ruff: noqa: E501

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260331_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_configuration",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("settings_json", sa.JSON(), nullable=False),
        sa.Column("gitlab_token_enc", sa.LargeBinary(), nullable=True),
        sa.Column("jira_token_enc", sa.LargeBinary(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_configuration")),
    )
    op.execute("INSERT INTO app_configuration (id, settings_json) VALUES (1, '{}'::json)")

    op.create_table(
        "repository",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("gitlab_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("default_branch", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repository")),
        sa.UniqueConstraint("gitlab_id", name=op.f("uq_repository_gitlab_id")),
    )

    op.create_table(
        "metric_snapshot",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("repository_id", sa.BigInteger(), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("period_type", sa.String(length=10), nullable=False),
        sa.Column("deployment_freq", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("lead_time_minutes", sa.Integer(), nullable=True),
        sa.Column("release_wait_median_minutes", sa.Integer(), nullable=True),
        sa.Column("change_failure_rate", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("mttr_minutes", sa.Integer(), nullable=True),
        sa.Column("mttr_alpha_minutes", sa.Integer(), nullable=True),
        sa.Column("lead_post_production_median_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repository.id"],
            name=op.f("fk_metric_snapshot_repository_id_repository"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_metric_snapshot")),
    )
    op.create_index(
        "ix_metric_snapshot_repository_period_type_period_start",
        "metric_snapshot",
        ["repository_id", "period_type", "period_start"],
        unique=False,
    )

    op.create_table(
        "merge_request",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("gitlab_mr_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("source_branch", sa.String(length=255), nullable=True),
        sa.Column("target_branch", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_commit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("head_sha", sa.String(length=40), nullable=True),
        sa.Column("merge_commit_sha", sa.String(length=40), nullable=True),
        sa.Column("squash_commit_sha", sa.String(length=40), nullable=True),
        sa.Column("effective_commit_sha", sa.String(length=40), nullable=True),
        sa.Column("jira_key", sa.String(length=50), nullable=True),
        sa.Column("jira_key_source", sa.String(length=15), nullable=True),
        sa.Column("first_customer_tag", sa.String(length=255), nullable=True),
        sa.Column("first_customer_tag_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_wait_time_hours", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("lead_time_hours", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("lead_post_production_hours", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("lead_time_match_status", sa.String(length=50), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repository.id"],
            name=op.f("fk_merge_request_repository_id_repository"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_merge_request")),
    )
    op.create_index("ix_merge_request_effective_commit_sha", "merge_request", ["effective_commit_sha"])
    op.create_index("ix_merge_request_jira_key", "merge_request", ["jira_key"])
    op.create_index(
        "ix_merge_request_repository_first_commit_at",
        "merge_request",
        ["repository_id", "first_commit_at"],
    )
    op.create_index("ix_merge_request_repository_merged_at", "merge_request", ["repository_id", "merged_at"])
    op.create_index(
        "ix_merge_request_repository_target_branch_merged_at",
        "merge_request",
        ["repository_id", "target_branch", "merged_at"],
    )
    op.create_index(
        "ix_merge_request_repository_gitlab_mr_unique",
        "merge_request",
        ["repository_id", "gitlab_mr_id"],
        unique=True,
    )

    op.create_table(
        "production_bug",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("jira_key", sa.String(length=50), nullable=False),
        sa.Column("summary", sa.String(length=1024), nullable=True),
        sa.Column("issue_type", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=True),
        sa.Column("priority", sa.String(length=50), nullable=True),
        sa.Column("components", sa.JSON(), nullable=True),
        sa.Column("affects_versions", sa.JSON(), nullable=True),
        sa.Column("fix_versions", sa.JSON(), nullable=True),
        sa.Column("parent_key", sa.String(length=50), nullable=True),
        sa.Column("parent_type", sa.String(length=100), nullable=True),
        sa.Column("indicator_cf10114", sa.Text(), nullable=True),
        sa.Column("indicator_cf10123", sa.Text(), nullable=True),
        sa.Column("healthy", sa.Boolean(), nullable=False),
        sa.Column("healthmemo", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mttr_minutes", sa.Integer(), nullable=True),
        sa.Column("first_fix_release_tag", sa.String(length=255), nullable=True),
        sa.Column("first_fix_release_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mttr_alpha_resolution_path", sa.String(length=20), nullable=True),
        sa.Column("mttr_alpha_minutes", sa.Integer(), nullable=True),
        sa.Column("ready_for_qa_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_worklog_seconds", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_production_bug")),
        sa.UniqueConstraint("jira_key", name=op.f("uq_production_bug_jira_key")),
    )
    op.create_index("ix_production_bug_created_closed", "production_bug", ["created_at", "closed_at"])
    op.create_index("ix_production_bug_healthy_created", "production_bug", ["healthy", "created_at"])
    op.create_index(
        "ix_production_bug_healthy_priority_created",
        "production_bug",
        ["healthy", "priority", "created_at"],
    )

    op.create_table(
        "release",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("repository_id", sa.BigInteger(), nullable=False),
        sa.Column("tag_name", sa.String(length=255), nullable=False),
        sa.Column("version_major", sa.Integer(), nullable=True),
        sa.Column("version_minor", sa.Integer(), nullable=True),
        sa.Column("version_patch", sa.Integer(), nullable=True),
        sa.Column("pre_release", sa.String(length=50), nullable=True),
        sa.Column("customer_release", sa.Boolean(), nullable=False),
        sa.Column("commit_sha", sa.String(length=40), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repository.id"],
            name=op.f("fk_release_repository_id_repository"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_release")),
    )
    op.create_index("ix_release_repository_id", "release", ["repository_id"])
    op.create_index("ix_release_customer_committed_at", "release", ["customer_release", "committed_at"])
    op.create_index("ix_release_repository_committed_at", "release", ["repository_id", "committed_at"])
    op.create_index("ix_release_repo_tag_unique", "release", ["repository_id", "tag_name"], unique=True)

    op.create_table(
        "sync_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("records_processed", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_log")),
    )
    op.create_index("ix_sync_log_source_started_at", "sync_log", ["source", "started_at"])

    op.create_table(
        "bug_release",
        sa.Column("bug_id", sa.BigInteger(), nullable=False),
        sa.Column("release_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["bug_id"],
            ["production_bug.id"],
            name=op.f("fk_bug_release_bug_id_production_bug"),
        ),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["release.id"],
            name=op.f("fk_bug_release_release_id_release"),
        ),
        sa.PrimaryKeyConstraint("bug_id", "release_id", name=op.f("pk_bug_release")),
    )

    op.create_table(
        "issue_worklog",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("bug_id", sa.BigInteger(), nullable=False),
        sa.Column("jira_worklog_id", sa.String(length=32), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("started", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_spent_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["bug_id"],
            ["production_bug.id"],
            name=op.f("fk_issue_worklog_bug_id_production_bug"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_issue_worklog")),
    )
    op.create_index("ix_issue_worklog_bug_id", "issue_worklog", ["bug_id"])
    op.create_index(
        "ix_issue_worklog_bug_jira_worklog_unique",
        "issue_worklog",
        ["bug_id", "jira_worklog_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_issue_worklog_bug_jira_worklog_unique", table_name="issue_worklog")
    op.drop_index("ix_issue_worklog_bug_id", table_name="issue_worklog")
    op.drop_table("issue_worklog")
    op.drop_table("bug_release")
    op.drop_index("ix_sync_log_source_started_at", table_name="sync_log")
    op.drop_table("sync_log")
    op.drop_index("ix_release_repo_tag_unique", table_name="release")
    op.drop_index("ix_release_repository_committed_at", table_name="release")
    op.drop_index("ix_release_customer_committed_at", table_name="release")
    op.drop_index("ix_release_repository_id", table_name="release")
    op.drop_table("release")
    op.drop_index("ix_production_bug_healthy_priority_created", table_name="production_bug")
    op.drop_index("ix_production_bug_healthy_created", table_name="production_bug")
    op.drop_index("ix_production_bug_created_closed", table_name="production_bug")
    op.drop_table("production_bug")
    op.drop_index("ix_merge_request_repository_gitlab_mr_unique", table_name="merge_request")
    op.drop_index("ix_merge_request_repository_target_branch_merged_at", table_name="merge_request")
    op.drop_index("ix_merge_request_repository_merged_at", table_name="merge_request")
    op.drop_index("ix_merge_request_repository_first_commit_at", table_name="merge_request")
    op.drop_index("ix_merge_request_jira_key", table_name="merge_request")
    op.drop_index("ix_merge_request_effective_commit_sha", table_name="merge_request")
    op.drop_table("merge_request")
    op.drop_index(
        "ix_metric_snapshot_repository_period_type_period_start",
        table_name="metric_snapshot",
    )
    op.drop_table("metric_snapshot")
    op.drop_table("repository")
    op.drop_table("app_configuration")
