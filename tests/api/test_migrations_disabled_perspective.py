"""Regression tests for SQLite backfills when migrations are disabled."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from theo.services.api.app.core import database as database_module
from theo.services.api.app.db import seeds as seeds_module


def test_seed_contradictions_backfills_perspective(
    tmp_path: Path, monkeypatch
) -> None:
    """Ensure the perspective column exists even when migrations are disabled."""

    db_path = tmp_path / "legacy.sqlite"
    legacy_engine = create_engine(f"sqlite:///{db_path}")
    try:
        with legacy_engine.begin() as connection:
                connection.exec_driver_sql(
                    """
                    CREATE TABLE contradiction_seeds (
                        id TEXT PRIMARY KEY,
                        osis_a TEXT NOT NULL,
                        osis_b TEXT NOT NULL,
                        summary TEXT,
                        source TEXT,
                        tags TEXT,
                        weight FLOAT,
                        start_verse_id_a INTEGER,
                        end_verse_id_a INTEGER,
                        start_verse_id INTEGER,
                        end_verse_id INTEGER,
                        start_verse_id_b INTEGER,
                        end_verse_id_b INTEGER,
                        created_at DATETIME
                    );
                    """
                )
        with legacy_engine.connect() as connection:
            result = connection.exec_driver_sql("PRAGMA table_info('contradiction_seeds')")
            assert all(row[1] != "perspective" for row in result)
    finally:
        legacy_engine.dispose()

    engine = create_engine(
        f"sqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    database_module._engine = engine  # type: ignore[attr-defined]
    database_module._SessionLocal = sessionmaker(  # type: ignore[attr-defined]
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )

    statements: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _capture_statement(
        conn, cursor, statement, parameters, context, executemany
    ) -> None:
        statements.append(statement)

    monkeypatch.setattr(seeds_module, "seed_harmony_claims", lambda session: None)
    monkeypatch.setattr(
        seeds_module, "seed_commentary_excerpts", lambda session: None
    )
    monkeypatch.setattr(seeds_module, "seed_geo_places", lambda session: None)
    monkeypatch.setattr(seeds_module, "seed_openbible_geo", lambda session: None)

    try:
        with Session(engine) as session:
            seeds_module.seed_reference_data(session)

        with engine.connect() as connection:
            count = connection.exec_driver_sql(
                "SELECT COUNT(*) FROM contradiction_seeds"
            ).scalar_one()
            assert count > 0
            result = connection.exec_driver_sql(
                "PRAGMA table_info('contradiction_seeds')"
            )
            assert any(row[1] == "perspective" for row in result)

        assert any(
            "ALTER TABLE \"contradiction_seeds\" ADD COLUMN perspective TEXT" in stmt
            for stmt in statements
        )
    finally:
        event.remove(engine, "before_cursor_execute", _capture_statement)
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]

        for residual in db_path.parent.glob(f"{db_path.name}*"):
            residual.unlink(missing_ok=True)
