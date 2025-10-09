"""Execute raw SQL migrations against the configured database engine."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from pathlib import Path
from typing import Iterable

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ..core.database import get_engine
from .models import AppSetting

logger = logging.getLogger(__name__)

MIGRATIONS_PATH = Path(__file__).resolve().parent / "migrations"
_MIGRATION_KEY_PREFIX = "db:migration:"


def _iter_migration_files(migrations_path: Path) -> Iterable[Path]:
    if not migrations_path.exists():
        return []
    return sorted(
        path
        for path in migrations_path.iterdir()
        if path.is_file() and path.suffix.lower() == ".sql"
    )


def _migration_key(filename: str) -> str:
    return f"{_MIGRATION_KEY_PREFIX}{filename}"


def _requires_autocommit(sql: str) -> bool:
    return "CONCURRENTLY" in sql.upper()


def _execute_autocommit(engine: Engine, sql: str) -> None:
    statements = [part.strip() for part in sql.split(";") if part.strip()]
    if not statements:
        return

    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)


_SQLITE_PERSPECTIVE_MIGRATION = "20250129_add_perspective_to_contradiction_seeds.sql"


def _sqlite_has_column(engine: Engine, table: str, column: str) -> bool:
    """Return True when the provided SQLite table already defines the column."""

    with engine.connect() as connection:
        result = connection.exec_driver_sql(f"PRAGMA table_info('{table}')")
        for row in result:
            # SQLite pragma rows expose column name at index 1
            if len(row) > 1 and row[1] == column:
                return True
    return False


def run_sql_migrations(
    engine: Engine | None = None,
    migrations_path: Path | None = None,
    *,
    force: bool = False,
) -> list[str]:
    """Apply raw SQL migrations to the active database engine."""

    if engine is None:
        engine = get_engine()

    if migrations_path is None:
        migrations_path = MIGRATIONS_PATH

    dialect_name = getattr(engine.dialect, "name", None)
    supported_dialects = {"postgresql", "sqlite"}
    if not force and dialect_name not in supported_dialects:
        logger.debug(
            "Skipping SQL migrations for unsupported dialect: %s", dialect_name
        )
        return []

    applied: list[str] = []
    migration_files = list(_iter_migration_files(migrations_path))
    if not migration_files:
        return applied

    with Session(engine) as session:
        for path in migration_files:
            migration_name = path.name
            key = _migration_key(migration_name)
            if session.get(AppSetting, key):
                continue

            sql = path.read_text(encoding="utf-8")
            if not sql.strip():
                logger.debug("Skipping empty migration file: %s", migration_name)
                session.add(
                    AppSetting(
                        key=key,
                        value={
                            "applied_at": datetime.now(UTC).isoformat(),
                            "filename": migration_name,
                        },
                    )
                )
                session.commit()
                applied.append(migration_name)
                continue

            should_execute = True
            # Skip Postgres-only operations when using SQLite. These include
            # pgvector/tsvector types and index methods not supported by SQLite.
            if dialect_name == "sqlite":
                sql_upper = sql.upper()
                postgres_only_markers = (
                    "VECTOR(",        # pgvector type
                    "TSVECTOR",       # full text search type
                    "TO_TSVECTOR(",   # FTS function
                    "USING HNSW",     # pgvector index method
                    "VECTOR_L2_OPS",  # pgvector operator class
                    "USING GIN",      # Postgres index method
                    "USING GIST",     # Postgres index method
                )
                if any(marker in sql_upper for marker in postgres_only_markers):
                    logger.debug(
                        "Skipping migration %s for SQLite (Postgres-only constructs detected)",
                        migration_name,
                    )
                    should_execute = False

            if should_execute:
                logger.info("Applying SQL migration: %s", migration_name)
                if dialect_name == "postgresql" and _requires_autocommit(sql):
                    session.flush()
                    session.commit()
                    _execute_autocommit(engine, sql)
                else:
                    connection = session.connection()
                    connection.exec_driver_sql(sql)

            session.add(
                AppSetting(
                    key=key,
                    value={
                        "applied_at": datetime.now(UTC).isoformat(),
                        "filename": migration_name,
                    },
                )
            )
            session.commit()
            applied.append(migration_name)

    return applied
