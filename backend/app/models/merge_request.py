from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MergeRequest(Base):
    __tablename__ = "merge_request"
    __table_args__ = (
        Index("ix_merge_request_repository_first_commit_at", "repository_id", "first_commit_at"),
        Index("ix_merge_request_repository_merged_at", "repository_id", "merged_at"),
        Index(
            "ix_merge_request_repository_target_branch_merged_at",
            "repository_id",
            "target_branch",
            "merged_at",
        ),
        Index("ix_merge_request_effective_commit_sha", "effective_commit_sha"),
        Index("ix_merge_request_jira_key", "jira_key"),
        Index(
            "ix_merge_request_repository_gitlab_mr_unique",
            "repository_id",
            "gitlab_mr_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("repository.id"),
        nullable=False,
    )
    gitlab_mr_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str | None] = mapped_column(String(1024))
    description: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(255))
    source_branch: Mapped[str | None] = mapped_column(String(255))
    target_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_commit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    head_sha: Mapped[str | None] = mapped_column(String(40))
    merge_commit_sha: Mapped[str | None] = mapped_column(String(40))
    squash_commit_sha: Mapped[str | None] = mapped_column(String(40))
    effective_commit_sha: Mapped[str | None] = mapped_column(String(40))
    jira_key: Mapped[str | None] = mapped_column(String(50))
    jira_key_source: Mapped[str | None] = mapped_column(String(15))
    first_customer_tag: Mapped[str | None] = mapped_column(String(255))
    first_customer_tag_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_wait_time_hours: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    lead_time_hours: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    lead_post_production_hours: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    lead_time_match_status: Mapped[str | None] = mapped_column(String(50))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
