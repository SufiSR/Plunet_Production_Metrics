from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class IssueWorklog(Base):
    __tablename__ = "issue_worklog"
    __table_args__ = (
        Index("ix_issue_worklog_bug_id", "bug_id"),
        Index("ix_issue_worklog_bug_jira_worklog_unique", "bug_id", "jira_worklog_id", unique=True),
        Index("ix_issue_worklog_jira_account_id", "jira_account_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bug_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("production_bug.id"), nullable=False)
    jira_worklog_id: Mapped[str] = mapped_column(String(32), nullable=False)
    jira_account_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255))
    started: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    time_spent_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
