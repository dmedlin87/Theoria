from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from theo.adapters.persistence import Base, dispose_sqlite_engine
from theo.services.api.app.db.run_sql_migrations import run_sql_migrations

pytestmark = pytest.mark.schema


def test_run_sql_migrations_and_schema_validation(tmp_path: Path) -> None:
    """Apply SQL and Python migrations and ensure the schema reflects them."""

    engine = create_engine(f"sqlite:///{tmp_path / 'migrations.db'}", future=True)
    Base.metadata.create_all(engine)

    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    migrations_dir.joinpath("0001_create_demo.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS demo_records (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );
        """,
        encoding="utf-8",
    )
    migrations_dir.joinpath("0002_seed_demo.py").write_text(
        """
from sqlalchemy import text

def upgrade(*, session, engine):
    session.execute(text("INSERT INTO demo_records (id, name) VALUES (:id, :name)"), {"id": "seed", "name": "Seeded"})
    session.commit()
        """,
        encoding="utf-8",
    )

    applied = run_sql_migrations(engine, migrations_path=migrations_dir)
    assert applied == ["0001_create_demo.sql", "0002_seed_demo.py"]

    with Session(engine) as session:
        rows = session.execute(
            text("SELECT name FROM demo_records WHERE id = :id"), {"id": "seed"}
        ).all()
        assert rows == [("Seeded",)]

    reapplied = run_sql_migrations(engine, migrations_path=migrations_dir)
    assert reapplied == []

    engine.dispose()


def test_sqlite_engine_cleanup_allows_teardown(tmp_path: Path) -> None:
    """Ensure dispose_sqlite_engine releases file handles for teardown."""

    db_path = tmp_path / "teardown.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
    dispose_sqlite_engine(engine)
    engine.dispose()
    db_path.unlink()
    assert not db_path.exists()
