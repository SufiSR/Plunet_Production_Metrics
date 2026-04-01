from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def get_database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/dora_metrics",
    )


_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(get_database_url(), future=True)
    return _engine


_session_factory = sessionmaker(class_=Session, autoflush=False, autocommit=False)


def SessionLocal() -> Session:
    return _session_factory(bind=get_engine())
