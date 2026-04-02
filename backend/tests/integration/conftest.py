from __future__ import annotations

from collections.abc import Generator

import pytest
from alembic.config import Config
from testcontainers.postgres import PostgresContainer

from alembic import command


def _docker_daemon_reachable() -> bool:
    try:
        import docker

        docker.from_env().ping()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def postgres_url() -> Generator[str, None, None]:
    if not _docker_daemon_reachable():
        pytest.skip(
            "Docker daemon not reachable; integration tests need Docker for PostgreSQL.",
        )
    with PostgresContainer("postgres:16") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def migrated_database_url(postgres_url: str) -> str:
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", postgres_url)
    command.upgrade(alembic_cfg, "head")
    return postgres_url
