from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BugRelease(Base):
    __tablename__ = "bug_release"

    bug_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("production_bug.id", ondelete="CASCADE"),
        primary_key=True, nullable=False,
    )
    release_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("release.id", ondelete="CASCADE"),
        primary_key=True, nullable=False,
    )
