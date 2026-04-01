from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProductionBug(Base):
    __tablename__ = "production_bug"
    __table_args__ = (
        Index("ix_production_bug_created_closed", "created_at", "closed_at"),
        Index("ix_production_bug_healthy_created", "healthy", "created_at"),
        Index("ix_production_bug_healthy_priority_created", "healthy", "priority", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    jira_key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    summary: Mapped[str | None] = mapped_column(String(1024))
    issue_type: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str | None] = mapped_column(String(100))
    priority: Mapped[str | None] = mapped_column(String(50))
    components: Mapped[list[str] | None] = mapped_column(JSON)
    affects_versions: Mapped[list[str] | None] = mapped_column(JSON)
    fix_versions: Mapped[list[str] | None] = mapped_column(JSON)
    parent_key: Mapped[str | None] = mapped_column(String(50))
    parent_type: Mapped[str | None] = mapped_column(String(100))
    indicator_cf10114: Mapped[str | None] = mapped_column(Text)
    indicator_cf10123: Mapped[str | None] = mapped_column(Text)
    healthy: Mapped[bool] = mapped_column(Boolean, nullable=False)
    healthmemo: Mapped[str | None] = mapped_column(String(512))
    jira_created_at_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mttr_minutes: Mapped[int | None]
    first_fix_release_tag: Mapped[str | None] = mapped_column(String(255))
    first_fix_release_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mttr_alpha_resolution_path: Mapped[str | None] = mapped_column(String(20))
    mttr_alpha_minutes: Mapped[int | None]
    ready_for_qa_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_worklog_seconds: Mapped[int | None] = mapped_column(BigInteger)
