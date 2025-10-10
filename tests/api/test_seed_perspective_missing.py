"""Regression tests for seed loaders when ``perspective`` column is absent."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from theo.services.api.app.db.seeds import (
    seed_contradiction_claims,
    seed_harmony_claims,
)


@pytest.mark.parametrize(
    ("seed_fn", "table_name", "dataset_label"),
    [
        (seed_contradiction_claims, "contradiction_seeds", "contradiction"),
        (seed_harmony_claims, "harmony_seeds", "harmony"),
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

        with Session(engine) as session:
            with caplog.at_level(logging.WARNING):
                seed_fn(session)

        expected_message = (
            f"Skipping {dataset_label} seeds because 'perspective' column is missing"
        )
        assert expected_message in caplog.text
    finally:
        engine.dispose()
