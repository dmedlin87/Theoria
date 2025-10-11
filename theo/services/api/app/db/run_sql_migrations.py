"""Execute raw SQL migrations against the configured database engine."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
from pathlib import Path
from typing import Callable, Iterable

from sqlalchemy import inspect, or_
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ..core.database import get_engine
from ..ingest.metadata import compute_passage_osis_range
from .models import AppSetting, Passage

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
_PASSAGE_RANGE_MIGRATION = "20250315_passage_osis_verse_ids.sql"


def _normalise_passage_meta(meta: object) -> dict[str, object] | None:
    """Convert persisted passage metadata into a dictionary when possible."""

    if isinstance(meta, dict):
        return meta
    if isinstance(meta, str):
        try:
            loaded = json.loads(meta)
        except json.JSONDecodeError:
            return None
        if isinstance(loaded, dict):
            return loaded
    return None


def _run_passage_verse_backfill(engine: Engine, *, batch_size: int = 500) -> int:
    """Populate verse identifier ranges for existing passages in batches."""

    inspector = inspect(engine)
    if not inspector.has_table("passages"):
        return 0

    columns = {column["name"] for column in inspector.get_columns("passages")}
    required = {"osis_start_verse_id", "osis_end_verse_id"}
    if not required.issubset(columns):
        logger.debug(
            "Skipping passage verse backfill; required columns missing: %s",
            ", ".join(sorted(required - columns)),
        )
        return 0

    total_updated = 0
    skipped_ids: set[str] = set()

    with Session(engine) as session:
        while True:
            query = (
                session.query(Passage)
                .filter(
                    or_(
                        Passage.osis_start_verse_id.is_(None),
                        Passage.osis_end_verse_id.is_(None),
                    )
                )
                .filter(
                    or_(
                        Passage.osis_ref.isnot(None),
                        Passage.meta.isnot(None),
                    )
                )
                .order_by(Passage.id)
                .limit(batch_size)
            )
            if skipped_ids:
                query = query.filter(~Passage.id.in_(skipped_ids))

            batch = query.all()
            if not batch:
                break

            updated_in_batch = 0
            newly_skipped: list[str] = []

            for passage in batch:
                meta = _normalise_passage_meta(passage.meta)
                start_id, end_id = compute_passage_osis_range(passage.osis_ref, meta)
                if start_id is None or end_id is None:
                    newly_skipped.append(passage.id)
                    continue

                if (
                    passage.osis_start_verse_id == start_id
                    and passage.osis_end_verse_id == end_id
                ):
                    continue

                passage.osis_start_verse_id = start_id
                passage.osis_end_verse_id = end_id
                updated_in_batch += 1

            if updated_in_batch:
                session.commit()
                total_updated += updated_in_batch
            else:
                session.rollback()

            if newly_skipped:
                skipped_ids.update(newly_skipped)

            if len(batch) < batch_size:
                break

    return total_updated


_PYTHON_MIGRATIONS: list[tuple[str, Callable[[Engine], None]]] = [
    ("20250315_backfill_passage_osis_verse_ids.py", _run_passage_verse_backfill),
]


def _run_python_migrations(
    engine: Engine, *, force: bool = False
) -> list[str]:
    """Execute Python data migrations tracked alongside SQL scripts."""

    applied: list[str] = []

    with Session(engine) as session:
        for name, handler in _PYTHON_MIGRATIONS:
            key = _migration_key(name)
            existing_entry = session.get(AppSetting, key)
            if existing_entry and not force:
                continue

            logger.info("Applying Python migration: %s", name)
            handler(engine)

            session.merge(
                AppSetting(
                    key=key,
                    value={
                        "applied_at": datetime.now(UTC).isoformat(),
                        "filename": name,
                    },
                )
            )
            session.commit()
            applied.append(name)

    return applied


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

            skip_passage_range_for_sqlite = False
            if (
                dialect_name == "sqlite"
                and migration_name == _PASSAGE_RANGE_MIGRATION
            ):
                has_start = _sqlite_has_column(
                    engine, "passages", "osis_start_verse_id"
                )
                has_end = _sqlite_has_column(engine, "passages", "osis_end_verse_id")
                if has_start and has_end:
                    logger.debug(
                        "Skipping passage verse-id migration; columns already present on SQLite",
                    )
                    skip_passage_range_for_sqlite = True

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
                    "Skipping SQLite perspective migration; column already exists",
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

            if should_execute and not skip_passage_range_for_sqlite:
                logger.info("Applying SQL migration: %s", migration_name)
                if dialect_name == "postgresql" and _requires_autocommit(sql):
                    session.flush()
                    session.commit()
                    _execute_autocommit(engine, sql)
                else:
                    connection = session.connection()
                    if dialect_name == "sqlite":
                        for statement in _split_sql_statements(sql):
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

    applied.extend(_run_python_migrations(engine, force=force))
    return applied
