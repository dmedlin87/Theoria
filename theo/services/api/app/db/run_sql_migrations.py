"""Execute raw SQL migrations against the configured database engine."""

from __future__ import annotations

from datetime import UTC, datetime
from inspect import signature
import importlib.util
import logging
import re
from pathlib import Path
import runpy
from types import ModuleType
from typing import Iterable

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ..core.database import get_engine
from .models import AppSetting

logger = logging.getLogger(__name__)

MIGRATIONS_PATH = Path(__file__).resolve().parent / "migrations"
_MIGRATION_KEY_PREFIX = "db:migration:"


_SUPPORTED_EXTENSIONS = {".sql", ".py"}


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
_SQLITE_ADD_COLUMN_RE = re.compile(
    r"^ALTER\s+TABLE\s+(?P<table>[^\s]+)\s+ADD\s+COLUMN\s+(?P<column>[^\s]+)",
    re.IGNORECASE | re.DOTALL,
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
    for row in result:
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
            has_perspective_column = True
            if is_sqlite_perspective_migration:
                has_perspective_column = _sqlite_has_column(
                    engine, "contradiction_seeds", "perspective"
                )
                if not has_perspective_column:
                    logger.info(
                        "SQLite perspective column missing prior to migration; enforcing recreation"
                    )

            if existing_entry:
                if is_sqlite_perspective_migration and not has_perspective_column:
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
            if ( 
                is_sqlite_perspective_migration
                and has_perspective_column
                and existing_entry is None
            ):
                logger.debug(
                    "Skipping SQLite perspective migration; column already exists"
                )
                should_execute = False

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

            if should_execute:
                logger.info("Applying SQL migration: %s", migration_name)
                if dialect_name == "postgresql" and _requires_autocommit(sql):
                    session.flush()
                    session.commit()
                    _execute_autocommit(engine, sql)
                else:
                    connection = session.connection()
                    if dialect_name == "sqlite":
                        for statement in _split_sql_statements(sql):
                            if _sqlite_add_column_exists(connection, statement):
                                logger.debug(
                                    "Skipping SQLite migration statement; column already exists: %s",
                                    statement.strip(),
                                )
                                continue
                            connection.exec_driver_sql(statement)
                    else:
                        connection.exec_driver_sql(sql)

                if is_sqlite_perspective_migration:
                    recreated = _sqlite_has_column(
                        engine, "contradiction_seeds", "perspective"
                    )
                    if recreated:
                        logger.info(
                            "SQLite perspective column present after migration execution",
                        )
                    else:
                        logger.warning(
                            "SQLite perspective column still missing after migration execution",
                            )

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
