"""Regression tests for running raw SQL migrations against SQLite."""

from __future__ import annotations

from sqlalchemy import create_engine, inspect

from theo.services.api.app.db.models import AppSetting
from theo.services.api.app.db.run_sql_migrations import run_sql_migrations


def test_run_sql_migrations_applies_sqlite_columns(tmp_path) -> None:
    """Ensure migrations add the perspective column before seeding."""

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)

    # Provide the metadata tables required by the migration tracker.
    AppSetting.__table__.create(bind=engine)

    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE contradiction_seeds (
                id TEXT PRIMARY KEY,
                osis_a TEXT NOT NULL,
                osis_b TEXT NOT NULL,
                summary TEXT,
                source TEXT,
                tags JSON,
                weight FLOAT NOT NULL DEFAULT 1.0,
                created_at TIMESTAMP NOT NULL
            )
            """
        )

    sqlite_migrations = tmp_path / "migrations"
    sqlite_migrations.mkdir()

    migration_name = "0001_add_perspective.sql"
    sqlite_migrations.joinpath(migration_name).write_text(
        """
        ALTER TABLE contradiction_seeds
            ADD COLUMN perspective TEXT;
        """,
        encoding="utf-8",
    )

    applied = run_sql_migrations(engine, migrations_path=sqlite_migrations)

    assert migration_name in applied

    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("contradiction_seeds")}
    assert "perspective" in columns
