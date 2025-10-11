"""Regression tests for seed loaders when ``perspective`` column is absent."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from theo.services.api.app.db.seeds import (
    seed_contradiction_claims,
    seed_harmony_claims,
    seed_commentary_excerpts,
)


@pytest.mark.parametrize(
    ("seed_fn", "table_name", "dataset_label"),
    [
        (seed_contradiction_claims, "contradiction_seeds", "contradiction"),
        (seed_harmony_claims, "harmony_seeds", "harmony"),
        (seed_commentary_excerpts, "commentary_excerpt_seeds", "commentary excerpt"),
    ],
)
def test_seed_gracefully_handles_missing_perspective(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    seed_fn,
    table_name: str,
    dataset_label: str,
) -> None:
    """Ensure seeds exit cleanly when the ``perspective`` column is absent."""

    database_path = tmp_path / f"{table_name}.db"
    engine = create_engine(f"sqlite:///{database_path}")
    try:
        if table_name == "commentary_excerpt_seeds":
            columns = (
                "id TEXT PRIMARY KEY,"
                " osis TEXT NOT NULL,"
                " excerpt TEXT NOT NULL,"
                " source TEXT,"
                " title TEXT,"
                " tags TEXT"
            )
        else:
            columns = (
                "id TEXT PRIMARY KEY,"
                " osis_a TEXT NOT NULL,"
                " osis_b TEXT NOT NULL,"
                " summary TEXT,"
                " source TEXT,"
                " tags TEXT,"
                " weight FLOAT"
            )
        with engine.begin() as connection:
            connection.exec_driver_sql(
                f"CREATE TABLE {table_name} ({columns});"
            )

        statements: list[str] = []

        @event.listens_for(engine, "before_cursor_execute")
        def capture_sql(_, __, statement, ___, ____, _____) -> None:
            statements.append(statement)

        statements.clear()
        with Session(engine) as session:
            with caplog.at_level(logging.WARNING):
                seed_fn(session)

        expected_message = (
            f"Skipping {dataset_label} seeds because 'perspective' column is missing"
        )
        assert expected_message in caplog.text
        assert not any("ALTER TABLE" in statement.upper() for statement in statements)
    finally:
        engine.dispose()
