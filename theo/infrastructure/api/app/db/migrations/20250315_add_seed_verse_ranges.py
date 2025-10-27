"""Add verse range columns for seed tables."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

_SEED_COLUMN_MAP = {
    "contradiction_seeds": (
        "start_verse_id_a",
        "end_verse_id_a",
        "start_verse_id_b",
        "end_verse_id_b",
    ),
    "harmony_seeds": (
        "start_verse_id_a",
        "end_verse_id_a",
        "start_verse_id_b",
        "end_verse_id_b",
    ),
    "commentary_excerpt_seeds": (
        "start_verse_id",
        "end_verse_id",
    ),
}

_INDEX_DEFINITIONS = (
    ("ix_contradiction_seeds_range_a", "contradiction_seeds", ("start_verse_id_a", "end_verse_id_a")),
    ("ix_contradiction_seeds_range_b", "contradiction_seeds", ("start_verse_id_b", "end_verse_id_b")),
    ("ix_harmony_seeds_range_a", "harmony_seeds", ("start_verse_id_a", "end_verse_id_a")),
    ("ix_harmony_seeds_range_b", "harmony_seeds", ("start_verse_id_b", "end_verse_id_b")),
    ("ix_commentary_excerpt_seeds_range", "commentary_excerpt_seeds", ("start_verse_id", "end_verse_id")),
)


def _ensure_integer_column(connection: Connection, table: str, column: str) -> None:
    inspector = inspect(connection)
    existing = {col["name"] for col in inspector.get_columns(table)}
    if column in existing:
        return
    connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} INTEGER")


def _ensure_index(connection: Connection, name: str, table: str, columns: Iterable[str]) -> None:
    inspector = inspect(connection)
    existing_indexes = {index["name"] for index in inspector.get_indexes(table)}
    if name in existing_indexes:
        return
    column_clause = ", ".join(columns)
    connection.exec_driver_sql(
        f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({column_clause})"
    )


def upgrade(*, session: Session, engine) -> None:  # pragma: no cover - executed via migration runner
    bind = session.get_bind()
    if isinstance(bind, Connection):
        connection = bind
        close_connection = False
    else:
        connection = engine.connect()
        close_connection = True
    try:
        for table, columns in _SEED_COLUMN_MAP.items():
            for column in columns:
                _ensure_integer_column(connection, table, column)
        for name, table, columns in _INDEX_DEFINITIONS:
            _ensure_index(connection, name, table, columns)
    finally:
        if close_connection:
            connection.close()
    session.flush()
