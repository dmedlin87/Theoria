"""Idempotent seed loaders for research reference datasets."""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import yaml
from sqlalchemy import Table, delete, inspect
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateColumn

from theo.adapters.persistence.sqlite import dispose_sqlite_engine
from theo.services.geo import seed_openbible_geo
from ..ingest.osis import expand_osis_reference

from theo.services.api.app.persistence_models import (
    CommentaryExcerptSeed,
    ContradictionSeed,
    GeoPlace,
    HarmonySeed,
)

PROJECT_ROOT = Path(__file__).resolve().parents[5]
SEED_ROOT = PROJECT_ROOT / "data" / "seeds"
CONTRADICTION_NAMESPACE = uuid5(NAMESPACE_URL, "theo-engine/contradictions")
HARMONY_NAMESPACE = uuid5(NAMESPACE_URL, "theo-engine/harmonies")
COMMENTARY_NAMESPACE = uuid5(NAMESPACE_URL, "theo-engine/commentaries")

logger = logging.getLogger(__name__)

_DATASET_TABLES: dict[str, Table] = {
    "contradiction": ContradictionSeed.__table__,
    "harmony": HarmonySeed.__table__,
    "commentary excerpt": CommentaryExcerptSeed.__table__,
}

_MISSING_COLUMN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"no such column: (?:(?P<table>[\w\"'`]+)\.)?(?P<column>[\w\"'`]+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"has no column named (?:(?P<table>[\w\"'`]+)\.)?(?P<column>[\w\"'`]+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"column (?:(?P<table>[\w\"'`]+)\.)?(?P<column>[\w\"'`]+) does not exist",
        re.IGNORECASE,
    ),
    re.compile(
        r"unknown column ['\"](?:(?P<table>[\w\"'`]+)\.)?(?P<column>[\w\"'`]+)",
        re.IGNORECASE,
    ),
)


_dispose_sqlite_engine = dispose_sqlite_engine

def _load_structured(path: Path) -> list[dict]:
    if not path.exists():
        return []

    if path.suffix.lower() in {".yaml", ".yml"}:
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or []
    else:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    if isinstance(payload, dict):
        return list(payload.values())
    if isinstance(payload, list):
        return payload
    raise ValueError(f"Unsupported seed format for {path}")


def _coerce_list(value: object) -> list[str | None] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        result: list[str | None] = []
        for item in value:
            if item is None:
                result.append(None)
            else:
                result.append(str(item))
        return result or None
    return None


def _verse_bounds(reference: str | None) -> tuple[int | None, int | None]:
    if not reference:
        return (None, None)
    verse_ids = expand_osis_reference(str(reference))
    if not verse_ids:
        return (None, None)
    return (min(verse_ids), max(verse_ids))


def _iter_seed_entries(*paths: Path) -> list[dict]:
    entries: list[dict] = []
    for path in paths:
        if not path.exists():
            continue
        entries.extend(_load_structured(path))
    return entries


def _verse_range(reference: str | None) -> tuple[int, int] | None:
    if not reference:
        return None
    verse_ids = expand_osis_reference(str(reference))
    if not verse_ids:
        return None
    return min(verse_ids), max(verse_ids)


def _assign_range(record, start_attr: str, end_attr: str, reference: str | None) -> bool:
    changed = False
    verse_range = _verse_range(reference)
    start_value = verse_range[0] if verse_range else None
    end_value = verse_range[1] if verse_range else None
    if getattr(record, start_attr, None) != start_value:
        setattr(record, start_attr, start_value)
        changed = True
    if getattr(record, end_attr, None) != end_value:
        setattr(record, end_attr, end_value)
        changed = True
    return changed


def _get_session_connection(session: Session) -> tuple[Connection | None, bool]:
    """Return a connection bound to ``session`` and whether it should be closed."""

    bind = session.get_bind()
    if bind is None:
        return (None, False)

    if isinstance(bind, Engine):
        # ``session.connection()`` ensures we operate on the same DB handle that the
        # session will later use for ORM queries. This is essential for in-memory
        # SQLite databases where each new engine connection represents a fresh
        # database instance.
        return (session.connection(), False)

    return (bind, False)


def _table_exists(
    session: Session, table_name: str, *, schema: str | None = None
) -> bool:
    """Return ``True`` when ``table_name`` is present in the bound database."""

    connection, should_close = _get_session_connection(session)
    if connection is None:
        return False

    try:
        dialect_name = getattr(getattr(connection, "dialect", None), "name", None)
        if dialect_name == "sqlite":
            try:
                result = connection.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                )
            except Exception:  # pragma: no cover - defensive: unexpected SQLite errors
                return False
            return any(row and row[0] == table_name for row in result)

        inspector = inspect(connection)
        try:
            return inspector.has_table(table_name, schema=schema)
        except Exception:  # pragma: no cover - defensive: fall back to manual scan
            try:
                tables = inspector.get_table_names(schema=schema)
            except Exception:
                return False
            normalized = table_name.lower()
            return any((candidate or "").lower() == normalized for candidate in tables)
    finally:
        if should_close and connection is not None:
            connection.close()


def _table_has_column(
    session: Session, table_name: str, column_name: str, *, schema: str | None = None
) -> bool:
    """Check whether the bound database exposes ``column_name`` on ``table_name``."""

    connection, should_close = _get_session_connection(session)
    if connection is None:
        return False

    engine = None
    if hasattr(connection, "engine"):
        engine = connection.engine
    elif isinstance(connection, Connection):
        engine = connection
    dialect = getattr(connection, "dialect", None)
    dialect_name = getattr(dialect, "name", None)
    if dialect_name == "sqlite":
        database_name = getattr(getattr(engine, "url", None), "database", None) if engine else None
        if database_name and database_name != ":memory:":
            try:
                import sqlite3  # pragma: no cover - optional direct inspection
            except Exception:
                sqlite3 = None  # type: ignore[assignment]
            if sqlite3 is not None:
                try:
                    with sqlite3.connect(database_name) as raw_connection:
                        escaped_table = table_name.replace("'", "''")
                        cursor = raw_connection.execute(
                            f"PRAGMA table_info('{escaped_table}')"
                        )
                        for row in cursor:
                            if len(row) > 1 and row[1] == column_name:
                                return True
                        return False
                except Exception:  # pragma: no cover - defensive fallback
                    pass
        try:
            escaped_table = table_name.replace("'", "''")
            result = connection.exec_driver_sql(
                f"PRAGMA table_info('{escaped_table}')"
            )
            for row in result:
                if len(row) > 1 and row[1] == column_name:
                    return True
            return False
        except Exception:  # pragma: no cover - defensive: unexpected SQLite errors
            return False
        finally:
            if should_close and connection is not None:
                connection.close()

    inspector = inspect(connection)
    try:
        columns = inspector.get_columns(table_name, schema=schema)
    except Exception:  # pragma: no cover - defensive: DB might be mid-migration
        return False

    return any(column.get("name") == column_name for column in columns)


def _add_sqlite_columns(
    session: Session, table: Table, columns: Iterable[tuple[str, str]]
) -> bool:
    """Attempt to add *columns* with their SQL types to *table* when using SQLite."""

    connection, should_close = _get_session_connection(session)
    if connection is None:
        return False

    try:
        for column, column_type in columns:
            try:
                connection.exec_driver_sql(
                    f"ALTER TABLE {table.name} ADD COLUMN {column} {column_type}"
                )
            except OperationalError as exc:
                message = str(getattr(exc, "orig", exc)).lower()
                duplicate_indicators = (
                    "duplicate column name",
                    "already exists",
                )
                if any(indicator in message for indicator in duplicate_indicators):
                    continue
                return False
        return True
    finally:
        if should_close and connection is not None:
            connection.close()


def _recreate_seed_table_if_missing_column(
    session: Session,
    table: Table,
    column_name: str,
    *,
    dataset_label: str,
    force: bool = False,
) -> bool:
    """Drop and recreate ``table`` when ``column_name`` is absent."""

    if not force and _table_has_column(
        session, table.name, column_name, schema=table.schema
    ):
        return False

    bind = session.get_bind()
    if bind is None:
        return False

    engine = bind.engine if isinstance(bind, Connection) else bind
    if engine is None:
        return False

    session.rollback()
    try:
        with engine.begin() as connection:
            table.drop(bind=connection, checkfirst=True)
            table.create(bind=connection, checkfirst=False)
    except Exception:
        session.rollback()
        raise

    # Ensure subsequent ORM work reflects the rebuilt schema across connections.
    inspect(engine).clear_cache()
    engine.dispose()
    session.expire_all()
    return True


def _rebuild_perspective_column(
    session: Session,
    table: Table,
    *,
    dataset_label: str,
    log_suffix: str,
    force: bool = False,
) -> None:
    """Drop and recreate *table* when ``perspective`` is absent, logging the repair."""

    if _recreate_seed_table_if_missing_column(
        session,
        table,
        "perspective",
        dataset_label=dataset_label,
        force=force,
    ):
        logger.info(
            "Rebuilt %s table missing 'perspective' column; %s",
            table.name,
            log_suffix,
        )


def _ensure_perspective_column(
    session: Session,
    table: Table,
    dataset_label: str,
    *,
    required_columns: Iterable[str] | None = None,
    allow_repair: bool = False,
) -> bool:
    """Verify the ``perspective`` column exists before reading from ``table``."""

    dependencies = tuple(required_columns or ())
    required = ("perspective", *dependencies)
    missing = [
        column
        for column in required
        if not _table_has_column(session, table.name, column, schema=table.schema)
    ]
    if "perspective" in missing:
        session.rollback()
        logger.warning(
            "Skipping %s seeds because 'perspective' column is missing",
            dataset_label,
        )
        return False

    if not missing:
        return True

    if allow_repair:
        _rebuild_perspective_column(
            session,
            table,
            dataset_label=dataset_label,
            log_suffix=f"retrying {dataset_label} seeds",
            force=True,
        )
        missing = [
            column
            for column in required
            if not _table_has_column(session, table.name, column, schema=table.schema)
        ]
        if not missing:
            return True

    session.rollback()
    formatted = ", ".join(sorted(missing))
    logger.warning(
        "Skipping %s seeds because required column(s) are missing: %s",
        dataset_label,
        formatted,
    )
    return False


def _ensure_range_columns(
    session: Session, table: Table, dataset_label: str, columns: Iterable[str]
) -> bool:
    missing = [
        column
        for column in columns
        if not _table_has_column(session, table.name, column, schema=table.schema)
    ]
    if not missing:
        return True

    bind = session.get_bind()
    dialect_name = getattr(getattr(bind, "dialect", None), "name", None)
    if dialect_name == "sqlite":
        if _add_sqlite_columns(
            session,
            table,
            ((column, "INTEGER") for column in missing),
        ):
            remaining = [
                column
                for column in columns
                if not _table_has_column(
                    session, table.name, column, schema=table.schema
                )
            ]
            if not remaining:
                return True
            missing = remaining

    session.rollback()
    formatted = ", ".join(sorted(missing))
    logger.warning(
        "Skipping %s seeds because verse range column(s) are missing: %s",
        dataset_label,
        formatted,
    )
    return False


def _extract_missing_column_name(message: str, table_name: str) -> str | None:
    """Best-effort extraction of the missing column name from *message*."""

    normalized_table = table_name.strip("\"'`[]").lower()
    for pattern in _MISSING_COLUMN_PATTERNS:
        match = pattern.search(message)
        if not match:
            continue
        column = match.group("column")
        if not column:
            continue
        table_in_message = match.groupdict().get("table")
        if table_in_message:
            candidate_table = table_in_message.strip("\"'`[]").lower()
            if candidate_table and candidate_table != normalized_table:
                continue
        return column.strip("\"'`[]")
    return None


def _add_missing_column(
    session: Session, table: Table, column_name: str, *, dataset_label: str
) -> bool:
    """Attempt to add ``column_name`` to ``table`` via ``ALTER TABLE``."""

    column = table.c.get(column_name)
    if column is None:
        return False

    bind = session.get_bind()
    if bind is None:
        return False

    engine = bind.engine if isinstance(bind, Connection) else bind
    if engine is None:
        return False

    session.rollback()
    statement = f'ALTER TABLE "{table.name}" ADD COLUMN '
    try:
        column_ddl = str(CreateColumn(column).compile(dialect=engine.dialect))
    except Exception:
        return False
    statement += column_ddl

    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(statement)
    except OperationalError as exc:
        message = str(getattr(exc, "orig", exc)).lower()
        duplicate_indicators = ("duplicate column", "already exists")
        if any(indicator in message for indicator in duplicate_indicators):
            return True
        logger.debug(
            "Failed to add %s column to %s via ALTER TABLE: %s",
            column_name,
            table.name,
            exc,
        )
        return False
    else:
        inspect(engine).clear_cache()
        engine.dispose()
        session.expire_all()
        logger.info(
            "Added missing '%s' column to %s table for %s seeds",
            column_name,
            table.name,
            dataset_label,
        )
        return True


def _handle_missing_perspective_error(
    session: Session, dataset_label: str, exc: OperationalError
) -> bool:
    """Log, attempt repair, and rollback when required columns are missing."""

    raw_message = str(getattr(exc, "orig", exc))
    message = raw_message.lower()
    missing_indicators = (
        "no such column",
        "unknown column",
        "has no column named",
        "missing column",
        "column not found",
    )
    if not any(indicator in message for indicator in missing_indicators):
        return False

    session.rollback()

    table = _DATASET_TABLES.get(dataset_label)
    if table is not None:
        column_name = _extract_missing_column_name(raw_message, table.name)
        if column_name:
            if column_name.lower() == "perspective":
                logger.warning(
                    "Skipping %s seeds because 'perspective' column is missing",
                    dataset_label,
                )
                return True
            try:
                if _add_missing_column(
                    session, table, column_name, dataset_label=dataset_label
                ):
                    return True
                if _recreate_seed_table_if_missing_column(
                    session,
                    table,
                    column_name,
                    dataset_label=dataset_label,
                    force=True,
                ):
                    logger.info(
                        "Rebuilt %s table missing '%s' column after %s seed failure",
                        table.name,
                        column_name,
                        dataset_label,
                    )
                    return True
            except Exception:
                logger.exception(
                    "Failed to rebuild %s table after missing '%s' column",
                    table.name,
                    column_name,
                )

    if "perspective" in message:
        logger.warning(
            "Skipping %s seeds because 'perspective' column is missing",
            dataset_label,
        )
    else:
        logger.warning(
            "Skipping %s seeds because a required column is missing (%s)",
            dataset_label,
            raw_message,
        )
    return True


def _run_with_sqlite_lock_retry(
    session: Session,
    dataset_label: str,
    action: Callable[[Session], None],
    *,
    max_attempts: int = 10,
    backoff: float = 0.5,
) -> bool:
    """Execute ``action`` and commit, retrying when SQLite reports a lock."""

    bind = session.get_bind()

    for attempt in range(max_attempts):
        working_session = session if attempt == 0 else Session(bind=bind)
        try:
            action(working_session)
            working_session.commit()
            bind = working_session.get_bind()
            _dispose_sqlite_engine(bind)
            if working_session is not session:
                working_session.close()
            return True
        except OperationalError as exc:
            if _handle_missing_perspective_error(working_session, dataset_label, exc):
                bind = working_session.get_bind()
                _dispose_sqlite_engine(bind)
                if working_session is not session:
                    working_session.close()
                bind = session.get_bind()
                continue

            message = str(getattr(exc, "orig", exc)).lower()
            if "database is locked" in message or "database is busy" in message:
                logger.warning(
                    "Retrying %s seed commit due to SQLite lock (attempt %d/%d)",
                    dataset_label,
                    attempt + 1,
                    max_attempts,
                )
                working_session.rollback()
                _dispose_sqlite_engine(working_session.get_bind())
                if working_session is not session:
                    working_session.close()
                time.sleep(backoff * (attempt + 1))
                continue
            working_session.rollback()
            _dispose_sqlite_engine(working_session.get_bind())
            if working_session is not session:
                working_session.close()
            raise
        except Exception:
            working_session.rollback()
            _dispose_sqlite_engine(working_session.get_bind())
            if working_session is not session:
                working_session.close()
            raise
    logger.warning(
        "Aborting %s seed commit after repeated SQLite lock retries", dataset_label
    )
    return False


def _run_seed_with_perspective_guard(
    session: Session,
    seed_fn: Callable[[Session], None],
    dataset_label: str,
) -> None:
    """Execute *seed_fn* while gracefully handling missing perspective columns."""

    attempts = 0
    while True:
        try:
            seed_fn(session)
            return
        except OperationalError as exc:
            handled = _handle_missing_perspective_error(session, dataset_label, exc)
            if not handled:
                raise
            attempts += 1
            if attempts >= 2:
                return


def seed_contradiction_claims(session: Session) -> None:
    """Load contradiction seeds into the database in an idempotent manner."""

    table = ContradictionSeed.__table__
    try:
        perspective_ready = _ensure_perspective_column(
            session,
            table,
            "contradiction",
            required_columns=("created_at",)
            if hasattr(ContradictionSeed, "created_at")
            else None,
            allow_repair=False,
        )
    except OperationalError as exc:
        if _handle_missing_perspective_error(session, "contradiction", exc):
            return
        raise

    table_exists = _table_exists(session, table.name, schema=table.schema)
    if not perspective_ready and not table_exists:
        try:
            rebuilt = _recreate_seed_table_if_missing_column(
                session,
                table,
                "perspective",
                dataset_label="contradiction",
                force=True,
            )
        except OperationalError:
            session.rollback()
            logger.warning(
                "Skipping contradiction seeds because table recreation failed",
                exc_info=True,
            )
            return
        else:
            if rebuilt:
                logger.info(
                    "Created contradiction_seeds table before seeding bundled data",
                )
            perspective_ready = _table_has_column(
                session, table.name, "perspective", schema=table.schema
            )

    if not perspective_ready:
        return

    range_columns = [
        column
        for column in (
            "start_verse_id_a",
            "end_verse_id_a",
            "start_verse_id",
            "end_verse_id",
            "start_verse_id_b",
            "end_verse_id_b",
        )
        if hasattr(ContradictionSeed, column)
    ]
    if range_columns and not _ensure_range_columns(
        session,
        table,
        "contradiction",
        range_columns,
    ):
        return

    payload = _iter_seed_entries(
        SEED_ROOT / "contradictions.json",
        SEED_ROOT / "contradictions_additional.json",
        SEED_ROOT / "contradictions_catalog.yaml",
    )

    def _load(target_session: Session) -> None:
        seen_ids: set[str] = set()
        if not _table_has_column(
            target_session, table.name, "perspective", schema=table.schema
        ):
            target_session.rollback()
            logger.warning(
                "Skipping %s seeds because 'perspective' column is missing",
                "contradiction",
            )
            return
        try:
            for entry in payload:
                osis_a = entry.get("osis_a")
                osis_b = entry.get("osis_b")
                if not osis_a or not osis_b:
                    continue
                osis_a_value = str(osis_a)
                osis_b_value = str(osis_b)
                start_a, end_a = _verse_bounds(osis_a_value)
                start_b, end_b = _verse_bounds(osis_b_value)
                source = entry.get("source") or "community"
                perspective = (entry.get("perspective") or "skeptical").strip().lower()
                identifier = str(
                    uuid5(
                        CONTRADICTION_NAMESPACE,
                        "|".join(
                            [
                                str(osis_a).lower(),
                                str(osis_b).lower(),
                                source.lower(),
                                perspective,
                            ]
                        ),
                    )
                )
                seen_ids.add(identifier)
                record = target_session.get(ContradictionSeed, identifier)
                tags = _coerce_list(entry.get("tags"))
                weight = float(entry.get("weight", 1.0))
                summary = entry.get("summary")
                range_a = _verse_range(str(osis_a))
                range_b = _verse_range(str(osis_b))
                start_a = range_a[0] if range_a else None
                end_a = range_a[1] if range_a else None
                start_b = range_b[0] if range_b else None
                end_b = range_b[1] if range_b else None

                if record is None:
                    record_kwargs = {
                        "id": identifier,
                        "osis_a": osis_a_value,
                        "osis_b": osis_b_value,
                        "summary": summary,
                        "source": source,
                        "tags": tags,
                        "weight": weight,
                        "perspective": perspective,
                    }
                    if hasattr(ContradictionSeed, "start_verse_id_a"):
                        record_kwargs["start_verse_id_a"] = start_a
                    if hasattr(ContradictionSeed, "end_verse_id_a"):
                        record_kwargs["end_verse_id_a"] = end_a
                    if hasattr(ContradictionSeed, "start_verse_id"):
                        record_kwargs["start_verse_id"] = start_a
                    if hasattr(ContradictionSeed, "end_verse_id"):
                        record_kwargs["end_verse_id"] = end_a
                    if hasattr(ContradictionSeed, "start_verse_id_b"):
                        record_kwargs["start_verse_id_b"] = start_b
                    if hasattr(ContradictionSeed, "end_verse_id_b"):
                        record_kwargs["end_verse_id_b"] = end_b

                    record = ContradictionSeed(**record_kwargs)
                    target_session.add(record)
                else:
                    if record.osis_a != osis_a_value:
                        record.osis_a = osis_a_value
                    if record.osis_b != osis_b_value:
                        record.osis_b = osis_b_value
                    if record.summary != summary:
                        record.summary = summary
                    if record.source != source:
                        record.source = source
                    if record.tags != tags:
                        record.tags = tags
                    if record.weight != weight:
                        record.weight = weight
                    if record.perspective != perspective:
                        record.perspective = perspective
                    if hasattr(record, "start_verse_id_a") and record.start_verse_id_a != start_a:
                        record.start_verse_id_a = start_a
                    if hasattr(record, "end_verse_id_a") and record.end_verse_id_a != end_a:
                        record.end_verse_id_a = end_a
                    if hasattr(record, "start_verse_id_b") and record.start_verse_id_b != start_b:
                        record.start_verse_id_b = start_b
                    if hasattr(record, "end_verse_id_b") and record.end_verse_id_b != end_b:
                        record.end_verse_id_b = end_b
                    if hasattr(record, "start_verse_id") and hasattr(record, "end_verse_id"):
                        _assign_range(record, "start_verse_id", "end_verse_id", str(osis_a))
                    if hasattr(record, "start_verse_id_b") and hasattr(record, "end_verse_id_b"):
                        _assign_range(
                            record,
                            "start_verse_id_b",
                            "end_verse_id_b",
                            str(osis_b),
                        )
        except OperationalError as exc:
            if _handle_missing_perspective_error(
                target_session, "contradiction", exc
            ):
                return
            raise

        if seen_ids:
            target_session.execute(
                delete(ContradictionSeed).where(~ContradictionSeed.id.in_(seen_ids))
            )

    _run_with_sqlite_lock_retry(session, "contradiction", _load)


def seed_harmony_claims(session: Session) -> None:
    """Load harmony seeds from bundled YAML/JSON files."""

    table = HarmonySeed.__table__
    if not _ensure_perspective_column(
        session,
        table,
        "harmony",
        required_columns=("created_at",) if hasattr(HarmonySeed, "created_at") else None,
        allow_repair=True,
    ):
        return

    harmony_range_columns = [
        column
        for column in (
            "start_verse_id_a",
            "end_verse_id_a",
            "start_verse_id",
            "end_verse_id",
            "start_verse_id_b",
            "end_verse_id_b",
        )
        if hasattr(HarmonySeed, column)
    ]
    if harmony_range_columns and not _ensure_range_columns(
        session,
        table,
        "harmony",
        harmony_range_columns,
    ):
        return

    payload = _iter_seed_entries(
        SEED_ROOT / "harmonies.yaml",
        SEED_ROOT / "harmonies.json",
        SEED_ROOT / "harmonies_additional.yaml",
    )
    if not payload:
        return

    def _load(target_session: Session) -> None:
        seen_ids: set[str] = set()
        for entry in payload:
            osis_a = entry.get("osis_a")
            osis_b = entry.get("osis_b")
            summary = entry.get("summary")
            if not osis_a or not osis_b or not summary:
                continue
            osis_a_value = str(osis_a)
            osis_b_value = str(osis_b)
            start_a, end_a = _verse_bounds(osis_a_value)
            start_b, end_b = _verse_bounds(osis_b_value)
            source = entry.get("source") or "community"
            perspective = (entry.get("perspective") or "apologetic").strip().lower()
            identifier = str(
                uuid5(
                    HARMONY_NAMESPACE,
                    "|".join(
                        [
                            str(osis_a).lower(),
                            str(osis_b).lower(),
                            source.lower(),
                            perspective,
                        ]
                    ),
                )
            )
            seen_ids.add(identifier)
            record = target_session.get(HarmonySeed, identifier)
            tags = _coerce_list(entry.get("tags"))
            weight = float(entry.get("weight", 1.0))
            range_a = _verse_range(str(osis_a))
            range_b = _verse_range(str(osis_b))
            start_a = range_a[0] if range_a else None
            end_a = range_a[1] if range_a else None
            start_b = range_b[0] if range_b else None
            end_b = range_b[1] if range_b else None

            if record is None:
                record_kwargs = {
                    "id": identifier,
                    "osis_a": osis_a_value,
                    "osis_b": osis_b_value,
                    "summary": summary,
                    "source": source,
                    "tags": tags,
                    "weight": weight,
                    "perspective": perspective,
                }
                if hasattr(HarmonySeed, "start_verse_id_a"):
                    record_kwargs["start_verse_id_a"] = start_a
                if hasattr(HarmonySeed, "end_verse_id_a"):
                    record_kwargs["end_verse_id_a"] = end_a
                if hasattr(HarmonySeed, "start_verse_id"):
                    record_kwargs["start_verse_id"] = start_a
                if hasattr(HarmonySeed, "end_verse_id"):
                    record_kwargs["end_verse_id"] = end_a
                if hasattr(HarmonySeed, "start_verse_id_b"):
                    record_kwargs["start_verse_id_b"] = start_b
                if hasattr(HarmonySeed, "end_verse_id_b"):
                    record_kwargs["end_verse_id_b"] = end_b

                record = HarmonySeed(**record_kwargs)
                target_session.add(record)
            else:
                updated = False
                if record.osis_a != osis_a_value:
                    record.osis_a = osis_a_value
                    updated = True
                if record.osis_b != osis_b_value:
                    record.osis_b = osis_b_value
                    updated = True
                if record.summary != summary:
                    record.summary = summary
                    updated = True
                if record.source != source:
                    record.source = source
                    updated = True
                if record.tags != tags:
                    record.tags = tags
                    updated = True
                if record.weight != weight:
                    record.weight = weight
                    updated = True
                if record.perspective != perspective:
                    record.perspective = perspective
                    updated = True
                if hasattr(record, "start_verse_id_a") and record.start_verse_id_a != start_a:
                    record.start_verse_id_a = start_a
                    updated = True
                if hasattr(record, "end_verse_id_a") and record.end_verse_id_a != end_a:
                    record.end_verse_id_a = end_a
                    updated = True
                if hasattr(record, "start_verse_id_b") and record.start_verse_id_b != start_b:
                    record.start_verse_id_b = start_b
                    updated = True
                if hasattr(record, "end_verse_id_b") and record.end_verse_id_b != end_b:
                    record.end_verse_id_b = end_b
                if hasattr(record, "start_verse_id") and hasattr(record, "end_verse_id"):
                    if _assign_range(record, "start_verse_id", "end_verse_id", str(osis_a)):
                        updated = True
                if hasattr(record, "start_verse_id_b") and hasattr(record, "end_verse_id_b"):
                    if _assign_range(
                        record,
                        "start_verse_id_b",
                        "end_verse_id_b",
                        str(osis_b),
                    ):
                        updated = True
                if updated:
                    record.updated_at = datetime.now(UTC)

        if seen_ids:
            target_session.execute(delete(HarmonySeed).where(~HarmonySeed.id.in_(seen_ids)))

    _run_with_sqlite_lock_retry(session, "harmony", _load)


def seed_commentary_excerpts(session: Session) -> None:
    """Seed curated commentary excerpts into the catalogue."""

    table = CommentaryExcerptSeed.__table__
    if not _ensure_perspective_column(
        session,
        table,
        "commentary excerpt",
        required_columns=("created_at",)
        if hasattr(CommentaryExcerptSeed, "created_at")
        else None,
        allow_repair=True,
    ):
        return
    if not _ensure_range_columns(
        session,
        table,
        "commentary excerpt",
        ("start_verse_id", "end_verse_id"),
    ):
        return

    payload = _iter_seed_entries(
        SEED_ROOT / "commentaries.yaml",
        SEED_ROOT / "commentaries.json",
        SEED_ROOT / "commentaries_additional.yaml",
    )
    if not payload:
        return

    def _load(target_session: Session) -> None:
        seen_ids: set[str] = set()
        for entry in payload:
            osis = entry.get("osis")
            excerpt = entry.get("excerpt")
            if not osis or not excerpt:
                continue
            osis_value = str(osis)
            start_verse_id, end_verse_id = _verse_bounds(osis_value)
            source = entry.get("source") or "community"
            perspective = (entry.get("perspective") or "neutral").strip().lower()
            identifier = str(
                uuid5(
                    COMMENTARY_NAMESPACE,
                    "|".join([str(osis).lower(), source.lower(), perspective, excerpt[:64].lower()]),
                )
            )
            seen_ids.add(identifier)
            record = target_session.get(CommentaryExcerptSeed, identifier)
            tags = _coerce_list(entry.get("tags"))
            title = entry.get("title")
            verse_range = _verse_range(str(osis))
            start_value = verse_range[0] if verse_range else None
            end_value = verse_range[1] if verse_range else None

            if record is None:
                record = CommentaryExcerptSeed(
                    id=identifier,
                    osis=osis_value,
                    title=title,
                    excerpt=excerpt,
                    source=source,
                    perspective=perspective,
                    tags=tags,
                    start_verse_id=start_value,
                    end_verse_id=end_value,
                )
                target_session.add(record)
            else:
                updated = False
                if record.osis != osis_value:
                    record.osis = osis_value
                    updated = True
                if record.title != title:
                    record.title = title
                    updated = True
                if record.excerpt != excerpt:
                    record.excerpt = excerpt
                    updated = True
                if record.source != source:
                    record.source = source
                    updated = True
                if record.perspective != perspective:
                    record.perspective = perspective
                    updated = True
                if record.tags != tags:
                    record.tags = tags
                    updated = True
                if record.start_verse_id != start_verse_id:
                    record.start_verse_id = start_verse_id
                    updated = True
                if record.end_verse_id != end_verse_id:
                    record.end_verse_id = end_verse_id
                if _assign_range(record, "start_verse_id", "end_verse_id", str(osis)):
                    updated = True
                if updated:
                    record.updated_at = datetime.now(UTC)

        if seen_ids:
            target_session.execute(
                delete(CommentaryExcerptSeed).where(~CommentaryExcerptSeed.id.in_(seen_ids))
            )

    _run_with_sqlite_lock_retry(session, "commentary excerpt", _load)


def seed_geo_places(session: Session) -> None:
    """Load geographical reference data."""

    seed_path = SEED_ROOT / "geo_places.json"
    if not seed_path.exists():
        return

    payload = _load_structured(seed_path)
    if not payload:
        return

    def _load(target_session: Session) -> None:
        seen_slugs: set[str] = set()
        for entry in payload:
            slug = entry.get("slug")
            name = entry.get("name")
            if not slug or not name:
                continue
            aliases = _coerce_list(entry.get("aliases"))
            sources = entry.get("sources")
            confidence = entry.get("confidence")
            lat = entry.get("lat")
            lng = entry.get("lng")

            seen_slugs.add(str(slug))
            record = target_session.get(GeoPlace, slug)
            if record is None:
                record = GeoPlace(
                    slug=str(slug),
                    name=str(name),
                    lat=float(lat) if lat is not None else None,
                    lng=float(lng) if lng is not None else None,
                    confidence=float(confidence) if confidence is not None else None,
                    aliases=aliases,
                    sources=sources,
                )
                target_session.add(record)
            else:
                new_lat = float(lat) if lat is not None else None
                new_lng = float(lng) if lng is not None else None
                new_confidence = float(confidence) if confidence is not None else None

                changed = False
                if record.name != name:
                    record.name = str(name)
                    changed = True
                if record.lat != new_lat:
                    record.lat = new_lat
                    changed = True
                if record.lng != new_lng:
                    record.lng = new_lng
                    changed = True
                if record.confidence != new_confidence:
                    record.confidence = new_confidence
                    changed = True
                if record.aliases != aliases:
                    record.aliases = aliases
                    changed = True
                if record.sources != sources:
                    record.sources = sources
                    changed = True
                if changed:
                    record.updated_at = datetime.now(UTC)

        target_session.execute(
            delete(GeoPlace).where(~GeoPlace.slug.in_(seen_slugs))
        )

    _run_with_sqlite_lock_retry(session, "geo place", _load)




def _repair_missing_perspective_columns(session: Session) -> None:
    repairs: tuple[tuple[Table, str, str], ...] = (
        (ContradictionSeed.__table__, "contradiction", "contradiction seeds"),
        (HarmonySeed.__table__, "harmony", "harmony seeds"),
        (
            CommentaryExcerptSeed.__table__,
            "commentary excerpt",
            "commentary excerpts",
        ),
    )
    bind = session.get_bind()
    engine = bind.engine if isinstance(bind, Connection) else bind
    dialect_name = getattr(getattr(engine, "dialect", None), "name", None)
    for table, dataset_label, log_label in repairs:
        if _table_has_column(session, table.name, "perspective", schema=table.schema):
            continue

        repaired = False
        if dialect_name == "sqlite" and engine is not None:
            statement = f'ALTER TABLE "{table.name}" ADD COLUMN perspective TEXT'
            session.rollback()
            try:
                with engine.begin() as connection:
                    connection.exec_driver_sql(statement)
            except OperationalError as exc:
                message = str(getattr(exc, "orig", exc)).lower()
                duplicate_indicators = ("duplicate column name", "already exists")
                if not any(indicator in message for indicator in duplicate_indicators):
                    logger.warning(
                        "Failed to add perspective column to %s via ALTER TABLE: %s",
                        table.name,
                        exc,
                    )
                else:
                    repaired = True
            else:
                repaired = True
        if not repaired and _recreate_seed_table_if_missing_column(
            session, table, "perspective", dataset_label=dataset_label
        ):
            repaired = True

        if repaired:
            logger.info(
                "Rebuilt %s table missing 'perspective' column; reseeding %s",
                table.name,
                log_label,
            )
            session.expire_all()
            if engine is not None:
                engine.dispose()


def seed_reference_data(session: Session) -> None:
    """Entry point for loading all bundled reference datasets."""

    _repair_missing_perspective_columns(session)
    _run_seed_with_perspective_guard(session, seed_contradiction_claims, "contradiction")
    _run_seed_with_perspective_guard(session, seed_harmony_claims, "harmony")
    _run_seed_with_perspective_guard(session, seed_commentary_excerpts, "commentary excerpt")
    seed_geo_places(session)
    seed_openbible_geo(session)
