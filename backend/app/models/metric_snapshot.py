from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshot"
    __table_args__ = (
        Index(
            "ix_metric_snapshot_repository_period_type_period_start",
            "repository_id",
            "period_type",
            "period_start",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger()
        .with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    repository_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("repository.id"))
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)
    deployment_freq: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    lead_time_minutes: Mapped[int | None]
    release_wait_median_minutes: Mapped[int | None]
    change_failure_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    mttr_minutes: Mapped[int | None]
    mttr_alpha_minutes: Mapped[int | None]
    lead_post_production_median_minutes: Mapped[int | None]
    lead_time_sample_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lead_time_match_counts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
