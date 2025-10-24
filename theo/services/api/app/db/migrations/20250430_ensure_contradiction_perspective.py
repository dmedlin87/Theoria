"""Ensure contradiction seeds expose the perspective column."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy.orm import Session

from theo.adapters.persistence.models import ContradictionSeed


def _add_perspective_column(engine: Engine) -> None:
    statement = "ALTER TABLE contradiction_seeds ADD COLUMN perspective VARCHAR(255)"
    with engine.begin() as connection:
        connection.exec_driver_sql(statement)


def upgrade(*, session: Session, engine: Engine) -> None:  # pragma: no cover - executed via migration runner
    inspector = inspect(engine)

    try:
        columns = inspector.get_columns("contradiction_seeds")
    except NoSuchTableError:
        ContradictionSeed.__table__.create(bind=engine, checkfirst=True)
        session.flush()
        return

    if any(column.get("name") == "perspective" for column in columns):
        return

    dialect = getattr(engine.dialect, "name", "")
    if dialect == "sqlite":
        _add_perspective_column(engine)
    else:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE contradiction_seeds "
                    "ADD COLUMN perspective VARCHAR(255)"
                )
            )
    session.flush()
