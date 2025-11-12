"""Execute raw SQL migrations against the configured database engine."""

from __future__ import annotations

import importlib.util
import json
import logging
import re
import runpy
from datetime import UTC, datetime
from inspect import signature
from pathlib import Path
from types import ModuleType
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy.orm import Session

from theo.application.facades.database import get_engine
from theo.infrastructure.api.app.persistence_models import (
    AppSetting,
    ChatSession,
    ContradictionSeed,
)

logger = logging.getLogger(__name__)

MIGRATIONS_PATH = Path(__file__).resolve().parent / "migrations"
_MIGRATION_KEY_PREFIX = "db:migration:"


_SUPPORTED_EXTENSIONS = {".sql", ".py"}

_PERFORMANCE_INDEXES_POSTGRES = (
    {
        "name": "idx_passages_embedding_null",
        "table": "passages",
        "statement": (
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_passages_embedding_null "
            "ON passages (id) WHERE embedding IS NULL"
        ),
    },
    {
        "name": "idx_documents_updated_at",
        "table": "documents",
        "statement": (
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_updated_at "
            "ON documents (updated_at)"
        ),
    },
    {
        "name": "idx_passages_document_id",
        "table": "passages",
        "statement": (
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_passages_document_id "
            "ON passages (document_id)"
        ),
    },
)

_PERFORMANCE_INDEXES_GENERIC = (
    {
        "name": "idx_passages_embedding_null",
        "table": "passages",
        "statement": (
            "CREATE INDEX IF NOT EXISTS idx_passages_embedding_null "
            "ON passages (id) WHERE embedding IS NULL"
        ),
    },
    {
        "name": "idx_documents_updated_at",
        "table": "documents",
        "statement": (
            "CREATE INDEX IF NOT EXISTS idx_documents_updated_at ON documents (updated_at)"
        ),
    },
    {
        "name": "idx_passages_document_id",
        "table": "passages",
        "statement": (
            "CREATE INDEX IF NOT EXISTS idx_passages_document_id ON passages (document_id)"
        ),
    },
)


def _sqlite_table_columns(connection, table: str) -> set[str]:
    """Return the set of column names for *table* in a SQLite database."""

    rows = connection.exec_driver_sql(f"PRAGMA table_info('{table}')").fetchall()
    return {row[1] for row in rows if len(row) > 1}


def _ensure_performance_indexes(engine: Engine) -> list[str]:
    """Ensure critical query indexes exist across supported dialects."""

    created: list[str] = []
    dialect_name: str | None = None
    pending_postgres: list[dict[str, str]] = []

    with engine.connect() as connection:
        dialect_name = getattr(connection.dialect, "name", None)
        if dialect_name == "postgresql":
            for entry in _PERFORMANCE_INDEXES_POSTGRES:
                index_name = entry["name"]
                table_name = entry["table"]
                table_exists = connection.execute(
                    text("SELECT to_regclass(:table)"),
                    {"table": table_name},
                ).scalar()
                if not table_exists:
                    logger.debug(
                        "Skipping index %s; table %s missing", index_name, table_name
                    )
                    continue
                exists = connection.execute(
                    text("SELECT to_regclass(:name)"),
                    {"name": index_name},
                ).scalar()
                if exists:
                    continue
                pending_postgres.append(entry)
        elif dialect_name == "sqlite":
            for entry in _PERFORMANCE_INDEXES_GENERIC:
                index_name = entry["name"]
                table_name = entry["table"]
                table_exists = connection.execute(
                    text(
                        "SELECT 1 FROM sqlite_master "
                        "WHERE type='table' AND name=:name"
                    ),
                    {"name": table_name},
                ).scalar()
                if not table_exists:
                    logger.debug(
                        "Skipping index %s; table %s missing", index_name, table_name
                    )
                    continue
                if table_name == "passages":
                    columns = _sqlite_table_columns(connection, table_name)
                    if "embedding" not in columns:
                        logger.debug(
                            "Skipping index %s; column embedding missing on %s",
                            index_name,
                            table_name,
                        )
                        continue
                exists = connection.execute(
                    text(
                        "SELECT 1 FROM sqlite_master "
                        "WHERE type='index' AND name=:name"
                    ),
                    {"name": index_name},
                ).scalar()
                if exists:
                    continue
                connection.exec_driver_sql(entry["statement"])
                created.append(index_name)
        else:
            logger.debug(
                "Skipping performance index enforcement for unsupported dialect: %s",
                dialect_name,
            )
            return created

    if dialect_name == "postgresql":
        for entry in pending_postgres:
            index_name = entry["name"]
            with engine.connect().execution_options(
                isolation_level="AUTOCOMMIT"
            ) as autocommit_conn:
                autocommit_conn.exec_driver_sql(entry["statement"])
            created.append(index_name)

    return created


def _log_created_indexes(indexes: list[str]) -> None:
    if indexes:
        logger.info(
            "Ensured database indexes: %s", ", ".join(sorted(indexes))
        )


def _iter_migration_files(migrations_path: Path) -> Iterable[Path]:
    if not migrations_path.exists():
        return []
    return sorted(
        path
        for path in migrations_path.iterdir()
        if path.is_file() and path.suffix.lower() in _SUPPORTED_EXTENSIONS
    )


def _load_python_migration(path: Path) -> ModuleType:
    """Dynamically import a Python migration module."""

    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load migration module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def _split_sql_statements(sql: str) -> list[str]:
    """Split a raw SQL script into individual statements.

    SQLite's DB-API driver does not allow executing multiple statements at
    once. When running migrations against SQLite we therefore need to split
    the script manually. The implementation below keeps track of quoted
    strings, dollar-quoted blocks, and SQL comments so that semicolons inside
    them do not terminate the statement.
    """

    statements: list[str] = []
    buffer: list[str] = []
    in_single_quote = False
    in_double_quote = False
    in_line_comment = False
    in_block_comment = False
    dollar_quote: str | None = None
    length = len(sql)
    i = 0

    while i < length:
        char = sql[i]
        next_char = sql[i + 1] if i + 1 < length else ""

        if dollar_quote is not None:
            if sql.startswith(dollar_quote, i):
                buffer.append(dollar_quote)
                i += len(dollar_quote)
                dollar_quote = None
                continue
            buffer.append(char)
            i += 1
            continue

        if in_line_comment:
            buffer.append(char)
            if char == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            buffer.append(char)
            if char == "*" and next_char == "/":
                buffer.append(next_char)
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if not in_single_quote and not in_double_quote:
            if char == "-" and next_char == "-":
                buffer.append(char)
                buffer.append(next_char)
                in_line_comment = True
                i += 2
                continue
            if char == "/" and next_char == "*":
                buffer.append(char)
                buffer.append(next_char)
                in_block_comment = True
                i += 2
                continue

        if char == "'" and not in_double_quote:
            buffer.append(char)
            if in_single_quote and next_char == "'":
                buffer.append(next_char)
                i += 2
                continue
            in_single_quote = not in_single_quote
            i += 1
            continue

        if char == '"' and not in_single_quote:
            buffer.append(char)
            if in_double_quote and next_char == '"':
                buffer.append(next_char)
                i += 2
                continue
            in_double_quote = not in_double_quote
            i += 1
            continue

        if not in_single_quote and not in_double_quote and char == "$":
            end = i + 1
            while end < length and (sql[end].isalnum() or sql[end] == "_"):
                end += 1
            if end < length and sql[end] == "$":
                tag = sql[i : end + 1]
                buffer.append(tag)
                dollar_quote = tag
                i = end + 1
                continue

        if (
            char == ";"
            and not in_single_quote
            and not in_double_quote
            and not in_line_comment
            and not in_block_comment
        ):
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer.clear()
            i += 1
            continue

        buffer.append(char)
        i += 1

    statement = "".join(buffer).strip()
    if statement:
        statements.append(statement)

    return statements


_SQLITE_PERSPECTIVE_MIGRATION = "20250129_add_perspective_to_contradiction_seeds.sql"
_SQLITE_CHAT_GOALS_MIGRATION = "20250223_chat_goals.sql"
_SQLITE_ADD_COLUMN_RE = re.compile(
    r"^ALTER\s+TABLE\s+(?P<table>[^\s]+)\s+ADD\s+COLUMN\s+(?P<column>[^\s]+)",
    re.IGNORECASE | re.DOTALL,
)
_INGESTION_JOBS_TABLE_RE = re.compile(
    r"\bingestion_jobs\b",
    re.IGNORECASE,
)


def _sqlite_normalize_identifier(identifier: str) -> str:
    """Return the bare identifier name without surrounding quotes."""

    identifier = identifier.strip()
    if not identifier:
        return identifier
    if identifier[0] in {'"', "'", "`"} and identifier[-1] == identifier[0]:
        return identifier[1:-1]
    if identifier[0] == "[" and identifier[-1] == "]":
        return identifier[1:-1]
    return identifier


def _sqlite_table_has_column(connection, table: str, column: str) -> bool:
    """Return True if the SQLite table already defines the column."""

    table = _sqlite_normalize_identifier(table)
    column = _sqlite_normalize_identifier(column)
    escaped_table = table.replace('"', '""')
    result = connection.exec_driver_sql(f'PRAGMA table_info("{escaped_table}")')
    try:
        rows = list(result)
    finally:
        result.close()
    if not rows:
        exists_result = connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table,)
        )
        try:
            exists = exists_result.fetchone()
        finally:
            exists_result.close()
        if not exists:
            raise NoSuchTableError(table)
    for row in rows:
        if len(row) > 1 and row[1] == column:
            return True
    return False


def _sqlite_add_column_exists(connection, statement: str) -> bool:
    """Detect if an ALTER TABLE ADD COLUMN statement targets an existing column."""

    match = _SQLITE_ADD_COLUMN_RE.match(statement.strip())
    if not match:
        return False
    table = match.group("table")
    column = match.group("column")
    return _sqlite_table_has_column(connection, table, column)


def _sqlite_has_column(engine: Engine, table: str, column: str) -> bool:
    """Return True when the provided SQLite table already defines the column."""

    with engine.connect() as connection:
        return _sqlite_table_has_column(connection, table, column)


def _sqlite_table_exists(connection, table: str) -> bool:
    """Return ``True`` if the SQLite database defines *table*."""

    table = _sqlite_normalize_identifier(table)
    result = connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table,)
    )
    try:
        return result.fetchone() is not None
    finally:
        result.close()


def _apply_sqlite_chat_goals_migration(session: Session) -> bool:
    """Ensure the chat goals schema migration is applied for SQLite."""

    try:
        connection = session.connection()
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.debug(
            "Unable to inspect chat_sessions table prior to goals migration",
            exc_info=exc,
        )
        return False

    mutated_schema = False
    if not _sqlite_table_exists(connection, "chat_sessions"):
        logger.info("Creating chat_sessions table for SQLite database")
        ChatSession.__table__.create(bind=connection, checkfirst=True)
        mutated_schema = True

    if not _sqlite_table_has_column(connection, "chat_sessions", "goals"):
        logger.info("Adding chat_sessions.goals column for SQLite database")
        connection.exec_driver_sql(
            "ALTER TABLE chat_sessions ADD COLUMN goals TEXT NOT NULL DEFAULT '[]'"
        )
        mutated_schema = True

    # Normalise memory snippet payloads to include missing keys like the Postgres migration.
    data_mutated = False
    try:
        result = connection.exec_driver_sql(
            "SELECT id, memory_snippets FROM chat_sessions"
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(
            "Unable to inspect chat_sessions memory snippets during goals migration",
            exc_info=exc,
        )
    else:
        try:
            rows = list(result)
        finally:
            result.close()
        for row in rows:
            raw_snippets = row[1]
            if raw_snippets in (None, "", b""):
                continue
            parsed: list[dict[str, object]] | None = None
            try:
                if isinstance(raw_snippets, (bytes, bytearray)):
                    parsed = json.loads(raw_snippets.decode("utf-8"))
                elif isinstance(raw_snippets, str):
                    parsed = json.loads(raw_snippets)
                elif isinstance(raw_snippets, list):
                    parsed = raw_snippets
            except Exception:
                logger.debug(
                    "Skipping memory snippet normalisation for chat session %s", row[0],
                    exc_info=True,
                )
                parsed = None
            if not parsed:
                continue
            mutated = False
            normalised_entries: list[dict[str, object]] = []
            for entry in parsed:
                if not isinstance(entry, dict):
                    mutated = True
                    normalised_entries.append({"value": entry, "goal_id": None, "trail_id": None})
                    continue
                if "goal_id" not in entry:
                    entry = dict(entry)
                    entry["goal_id"] = None
                    mutated = True
                if "trail_id" not in entry:
                    if not mutated:
                        entry = dict(entry)
                    entry["trail_id"] = None
                    mutated = True
                normalised_entries.append(entry)
            if mutated:
                connection.exec_driver_sql(
                    "UPDATE chat_sessions SET memory_snippets = ? WHERE id = ?",
                    (json.dumps(normalised_entries), row[0]),
                )
                data_mutated = True

    if mutated_schema or data_mutated:
        session.commit()

    return True


_SQLITE_ADD_COLUMN_RE = re.compile(
    r"^\s*ALTER\s+TABLE\s+(?P<table>[^\s]+)\s+ADD\s+COLUMN\s+(?P<column>[^\s]+)",
    re.IGNORECASE,
)


def _normalize_identifier(identifier: str) -> str:
    """Strip SQLite identifier quoting and schema prefixes."""

    normalized = identifier.strip().strip("`\"[]")
    if "." in normalized:
        normalized = normalized.split(".")[-1]
    return normalized


def _sqlite_should_skip_statement(statement: str, *, engine: Engine) -> bool:
    """Return ``True`` when a SQLite statement should be skipped.

    SQLite raises ``OperationalError`` if ``ALTER TABLE ... ADD COLUMN`` is
    executed for a column that already exists.  Test fixtures often call
    ``Base.metadata.create_all`` before running migrations, which means schema
    additions may already be present.  Detect these idempotent column additions
    and silently skip them so the migration runner remains resilient.
    """

    match = _SQLITE_ADD_COLUMN_RE.match(statement)
    if not match:
        return False

    table = _normalize_identifier(match.group("table"))
    column = _normalize_identifier(match.group("column"))
    if _sqlite_has_column(engine, table, column):
        logger.debug(
            "Skipping SQLite column addition for %s.%s; column already exists",
            table,
            column,
        )
        return True
    return False


def _execute_python_migration(path: Path, *, session: Session, engine: Engine) -> None:
    """Execute a Python-based migration script."""

    module = runpy.run_path(str(path))
    upgrade = module.get("upgrade")
    if not callable(upgrade):
        upgrade = module.get("apply")
    if not callable(upgrade):
        raise RuntimeError(
            "Python migration %s must define an 'upgrade' or 'apply' callable"
            % path.name
        )

    parameters = signature(upgrade).parameters
    kwargs: dict[str, object] = {}
    if "session" in parameters:
        kwargs["session"] = session
    if "engine" in parameters:
        kwargs["engine"] = engine

    upgrade(**kwargs)


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

    # Ensure the migration ledger table exists even on a brand new database.
    # Without this, attempts to check for applied migrations would fail when the
    # SQLite database has not yet been initialised by SQLAlchemy metadata.
    AppSetting.__table__.create(bind=engine, checkfirst=True)

    applied: list[str] = []
    migration_files = list(_iter_migration_files(migrations_path))
    if not migration_files:
        _log_created_indexes(_ensure_performance_indexes(engine))
        return applied

    with Session(engine) as session:
        for path in migration_files:
            migration_name = path.name
            key = _migration_key(migration_name)

            existing_entry = session.get(AppSetting, key)

            is_sqlite_perspective_migration = (
                dialect_name == "sqlite"
                and migration_name == _SQLITE_PERSPECTIVE_MIGRATION
            )
            sqlite_missing_perspective = False
            if is_sqlite_perspective_migration:
                sqlite_missing_perspective = True
                try:
                    connection = session.connection()
                except Exception as exc:  # pragma: no cover - defensive
                    logger.debug(
                        "Unable to inspect SQLite contradiction seeds table prior to migration",  # noqa: E501
                        exc_info=exc,
                    )
                else:
                    try:
                        sqlite_missing_perspective = not _sqlite_table_has_column(
                            connection, "contradiction_seeds", "perspective"
                        )
                    except Exception as exc:  # pragma: no cover - defensive
                        logger.debug(
                            "SQLite perspective inspection failed prior to migration", exc_info=exc
                        )
                        sqlite_missing_perspective = True
                if sqlite_missing_perspective:
                    logger.info(
                        "SQLite perspective column missing prior to migration; enforcing recreation"
                    )

            if existing_entry:
                if is_sqlite_perspective_migration and sqlite_missing_perspective:
                    logger.info(
                        "Reapplying SQLite perspective migration; removing existing ledger entry"
                    )
                    session.delete(existing_entry)
                    session.commit()
                    existing_entry = None
                else:
                    continue

            suffix = path.suffix.lower()
            if suffix == ".py":
                logger.info("Applying Python migration: %s", migration_name)
                _execute_python_migration(path, session=session, engine=engine)
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
            should_record = False
            if (
                is_sqlite_perspective_migration
                and not sqlite_missing_perspective
                and existing_entry is None
            ):
                logger.debug(
                    "Skipping SQLite perspective migration; column already exists"
                )
                should_execute = False
                should_record = True

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
                    "JSONB",          # Postgres JSON storage
                    "TIMESTAMPTZ",    # Postgres timestamp with TZ
                    "::JSON",         # Postgres casting syntax
                    "::JSONB",        # Postgres casting syntax
                    "NOW()",          # Postgres-specific default
                    "DOUBLE PRECISION",  # Postgres float alias
                    "CONCURRENTLY",   # Concurrent index creation
                )
                if any(marker in sql_upper for marker in postgres_only_markers):
                    logger.debug(
                        "Skipping migration %s for SQLite (Postgres-only constructs detected)",
                        migration_name,
                    )
                    should_execute = False

            custom_sqlite_handler_applied = False
            if (
                dialect_name == "sqlite"
                and migration_name == _SQLITE_CHAT_GOALS_MIGRATION
            ):
                custom_sqlite_handler_applied = _apply_sqlite_chat_goals_migration(session)
                if custom_sqlite_handler_applied:
                    logger.debug(
                        "Applied SQLite fallback handler for chat goals migration",
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
                    sqlite_recreated_table = False
                    if (
                        dialect_name == "sqlite"
                        and is_sqlite_perspective_migration
                        and sqlite_missing_perspective
                    ):
                        connection.exec_driver_sql(
                            "DROP TABLE IF EXISTS contradiction_seeds"
                        )
                        ContradictionSeed.__table__.create(
                            bind=connection, checkfirst=False
                        )
                        # Recreating the contradiction seeds table from the ORM definition
                        # ensures the refreshed schema includes the ``perspective`` column.
                        # Once the table has been rebuilt there is nothing left for the raw
                        # ALTER TABLE statement to operate on, so we skip executing the SQL
                        # file entirely and allow the subsequent seeding pass to repopulate the
                        # table with the bundled data.
                        sqlite_recreated_table = True

                    if sqlite_recreated_table:
                        logger.debug(
                            "Skipped executing %s after rebuilding contradiction_seeds table",
                            migration_name,
                        )
                    elif dialect_name == "sqlite":
                        for statement in _split_sql_statements(sql):
                            if _INGESTION_JOBS_TABLE_RE.search(statement) and not _sqlite_table_exists(
                                connection, "ingestion_jobs"
                            ):
                                logger.debug(
                                    "Skipping SQLite migration statement; missing table ingestion_jobs: %s",
                                    statement.strip(),
                                )
                                continue
                            if _sqlite_add_column_exists(connection, statement):
                                logger.debug(
                                    "Skipping SQLite migration statement; column already exists: %s",
                                    statement.strip(),
                                )
                                continue
                            connection.exec_driver_sql(statement)
                    else:
                        connection.exec_driver_sql(sql)

            if dialect_name == "sqlite" and is_sqlite_perspective_migration:
                try:
                    recreated = _sqlite_table_has_column(
                        session.connection(), "contradiction_seeds", "perspective"
                    )
                except Exception as exc:  # pragma: no cover - defensive
                    logger.debug(
                        "SQLite perspective inspection failed after migration", exc_info=exc
                    )
                    recreated = False
                if recreated:
                    logger.info(
                        "SQLite perspective column present after migration execution",
                    )
                else:
                    logger.warning(
                        "SQLite perspective column still missing after migration execution",
                    )

            if should_execute or custom_sqlite_handler_applied or should_record:
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

    created_indexes = _ensure_performance_indexes(engine)
    _log_created_indexes(created_indexes)

    return applied
