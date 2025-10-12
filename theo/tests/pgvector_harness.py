"""Reusable pytest plugin providing pgvector Testcontainer fixtures."""

from __future__ import annotations

import contextlib
import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

POSTGRES_IMAGE = os.environ.get("PYTEST_PGVECTOR_IMAGE", "ankane/pgvector:0.5.2")


def pytest_addoption(parser: pytest.Parser) -> None:
    """Expose CLI option enabling the pgvector-backed database harness."""

    parser.addoption(
        "--use-pgvector",
        action="store_true",
        default=False,
        dest="use_pgvector",
        help="Back API tests with a Postgres+pgvector Testcontainer instead of SQLite.",
    )


@pytest.fixture(scope="session")
def pgvector_container() -> Generator["PostgresContainer", None, None]:
    """Launch a pgvector-enabled Postgres container for integration tests."""

    try:
        from testcontainers.postgres import PostgresContainer
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        pytest.skip(f"testcontainers not installed: {exc}")

    container = PostgresContainer(image=POSTGRES_IMAGE)
    container.with_env("POSTGRES_DB", "theo")
    container.with_env("POSTGRES_USER", "postgres")
    container.with_env("POSTGRES_PASSWORD", "postgres")

    try:
        container.start()
    except Exception as exc:  # pragma: no cover - surfaced when Docker unavailable
        pytest.skip(f"Unable to start Postgres Testcontainer: {exc}")

    try:
        yield container
    finally:
        with contextlib.suppress(Exception):
            container.stop()


def _normalise_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


@pytest.fixture(scope="session")
def pgvector_database_url(pgvector_container) -> Generator[str, None, None]:
    """Yield a SQLAlchemy-friendly database URL for the running container."""

    raw_url = pgvector_container.get_connection_url()
    url = _normalise_database_url(raw_url)
    engine = create_engine(url, future=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        yield url
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def pgvector_engine(pgvector_database_url: str) -> Generator[Engine, None, None]:
    """Provide a SQLAlchemy engine connected to the pgvector container."""

    engine = create_engine(pgvector_database_url, future=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def pgvector_migrated_database_url(pgvector_database_url: str) -> Generator[str, None, None]:
    """Apply SQL migrations to the pgvector database and return the connection URL."""

    from theo.services.api.app.db.run_sql_migrations import run_sql_migrations

    engine = create_engine(pgvector_database_url, future=True)
    try:
        run_sql_migrations(engine)
        yield pgvector_database_url
    finally:
        engine.dispose()
