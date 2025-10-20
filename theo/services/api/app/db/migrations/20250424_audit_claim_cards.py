from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session


def _ensure_json_column(connection: Connection, table: str, column: str) -> None:
    inspector = inspect(connection)
    existing_columns = {col["name"] for col in inspector.get_columns(table)}
    if column in existing_columns:
        return
    dialect = connection.dialect.name
    if dialect == "postgresql":
        column_type = "JSONB"
    else:
        column_type = "JSON"
    connection.exec_driver_sql(
        f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"
    )


def upgrade(*, session: Session, engine: Engine) -> None:  # pragma: no cover - executed via migration runner
    bind = session.get_bind()
    if isinstance(bind, Connection):
        connection = bind
        close_connection = False
    else:
        connection = engine.connect()
        close_connection = True
    try:
        _ensure_json_column(connection, "audit_logs", "claim_cards")
        _ensure_json_column(connection, "audit_logs", "audit_metadata")
    finally:
        if close_connection:
            connection.close()
    session.flush()
