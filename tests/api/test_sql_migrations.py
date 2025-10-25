from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import shutil
import sqlite3

import importlib

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from theo.application.facades import database as database_module
from theo.application.facades.database import Base, configure_engine, get_engine
from theo.application.facades.settings import get_settings
from theo.services.api.app.db import seeds as seeds_module
from theo.adapters.persistence.models import AppSetting
from theo.services.api.app.main import app
import theo.services.api.app.db.run_sql_migrations as migrations_module
from theo.services.api.app.db.run_sql_migrations import (
    MIGRATIONS_PATH,
    _SQLITE_PERSPECTIVE_MIGRATION,
    run_sql_migrations,
)
from theo.services.api.app.db.seeds import seed_contradiction_claims


@pytest.mark.enable_migrations
@pytest.mark.usefixtures("_bypass_authentication")
def test_sql_migrations_run_on_startup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "app.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    try:
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        (migrations_dir / "001_create_table.sql").write_text(
            "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, value TEXT);",
            encoding="utf-8",
        )
        (migrations_dir / "002_insert.sql").write_text(
            "INSERT INTO test_table (value) VALUES ('alpha');",
            encoding="utf-8",
        )

        migrations_module = importlib.import_module(
            "theo.services.api.app.db.run_sql_migrations"
        )

        monkeypatch.setattr(migrations_module, "MIGRATIONS_PATH", migrations_dir)
        monkeypatch.setattr(engine.dialect, "name", "postgresql", raising=False)
        monkeypatch.setattr(seeds_module, "seed_openbible_geo", lambda *_, **__: None)

        executed_statements: list[str] = []

        @event.listens_for(engine, "before_cursor_execute")
        def _capture_sql(_, __, statement, *___) -> None:
            if "test_table" in statement:
                executed_statements.append(statement.strip())

        with TestClient(app):
            pass

        assert any("CREATE TABLE IF NOT EXISTS test_table" in stmt for stmt in executed_statements)
        assert any("INSERT INTO test_table" in stmt for stmt in executed_statements)

        with Session(engine) as session:
            assert session.get(AppSetting, "db:migration:001_create_table.sql") is not None
            assert session.get(AppSetting, "db:migration:002_insert.sql") is not None

        executed_statements.clear()

        with TestClient(app):
            pass

        assert not any("INSERT INTO test_table" in stmt for stmt in executed_statements)
    finally:
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]


def test_cli_entry_point_invokes_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli_module = importlib.import_module("scripts.run_sql_migrations")

    class DummyEngine:
        pass

    captured: dict[str, object] = {}

    def _configure(url: str | None = None):
        captured["database_url"] = url
        return DummyEngine()

    def _run(engine, migrations_path=None, force=False):  # type: ignore[no-untyped-def]
        captured["engine"] = engine
        captured["migrations_path"] = migrations_path
        captured["force"] = force
        return ["20250115_watchlist_timestamp_indexes.sql"]

    monkeypatch.setattr(cli_module, "configure_engine", _configure)
    monkeypatch.setattr(cli_module, "run_sql_migrations", _run)

    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()

    exit_code = cli_module.main(
        [
            "--database-url",
            "postgresql://localhost/theo",  # pragma: allowlist secret
            "--path",
            str(migrations_dir),
            "--force",
        ]
    )

    assert exit_code == 0
    assert captured["database_url"] == "postgresql://localhost/theo"
    assert captured["migrations_path"] == migrations_dir
    assert captured["force"] is True
    assert isinstance(captured["engine"], DummyEngine)


def test_sqlite_reapplies_missing_perspective_migration(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()

    try:
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        shutil.copy(
            MIGRATIONS_PATH / _SQLITE_PERSPECTIVE_MIGRATION,
            migrations_dir / _SQLITE_PERSPECTIVE_MIGRATION,
        )

        with engine.begin() as connection:
            connection.exec_driver_sql(
                """
                CREATE TABLE contradiction_seeds (
                    id VARCHAR PRIMARY KEY,
                    osis_a VARCHAR NOT NULL,
                    osis_b VARCHAR NOT NULL,
                    summary TEXT,
                    source VARCHAR,
                    tags TEXT,
                    weight FLOAT,
                    created_at DATETIME
                );
                """
            )

        AppSetting.__table__.create(bind=engine, checkfirst=True)

        ledger_key = f"db:migration:{_SQLITE_PERSPECTIVE_MIGRATION}"
        with Session(engine) as session:
            session.add(
                AppSetting(
                    key=ledger_key,
                    value={
                        "applied_at": datetime.now(UTC).isoformat(),
                        "filename": _SQLITE_PERSPECTIVE_MIGRATION,
                    },
                )
            )
            session.commit()

        # Column should be absent prior to running migrations
        with engine.connect() as connection:
            result = connection.exec_driver_sql("PRAGMA table_info('contradiction_seeds')")
            assert all(row[1] != "perspective" for row in result)

        applied = run_sql_migrations(engine=engine, migrations_path=migrations_dir)
        assert _SQLITE_PERSPECTIVE_MIGRATION in applied

        with Session(engine) as session:
            try:
                seed_contradiction_claims(session)
            except OperationalError as exc:  # pragma: no cover - defensive assertion
                pytest.fail(f"seed_contradiction_claims raised OperationalError: {exc}")
    finally:
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]
        for residual in db_path.parent.glob(f"{db_path.name}*"):
            residual.unlink(missing_ok=True)


@pytest.mark.enable_migrations
def test_sqlite_startup_without_migrations_creates_contradiction_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "fresh_boot.db"

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    database_module._engine = None  # type: ignore[attr-defined]
    database_module._SessionLocal = None  # type: ignore[attr-defined]

    def _noop_migrations(*args, **kwargs):  # type: ignore[no-untyped-def]
        return []

    monkeypatch.setattr(migrations_module, "run_sql_migrations", _noop_migrations)
    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.lifecycle.run_sql_migrations",
        _noop_migrations,
    )

    try:
        with TestClient(app):
            pass

        engine = get_engine()
        with engine.connect() as connection:
            result = connection.exec_driver_sql("PRAGMA table_info('contradiction_seeds')")
            columns = [row[1] for row in result]
        assert "perspective" in columns
    finally:
        get_settings.cache_clear()
        engine = database_module._engine
        if engine is not None:
            engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]
        for residual in db_path.parent.glob(f"{db_path.name}*"):
            residual.unlink(missing_ok=True)


def test_sqlite_seed_loader_handles_disabled_migrations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "legacy_disabled.db"

    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE contradiction_seeds (
                id TEXT PRIMARY KEY,
                osis_a TEXT NOT NULL,
                osis_b TEXT NOT NULL,
                summary TEXT,
                source TEXT,
                tags TEXT,
                weight REAL,
                created_at TEXT
            );
            """
        )

    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()

    try:
        sample_payload = [
            {
                "osis_a": "Gen.1.1",
                "osis_b": "Gen.1.2",
                "summary": "Legacy row",
                "source": "test",
                "tags": ["regression"],
                "weight": 1.0,
                "perspective": "skeptical",
            }
        ]

        monkeypatch.setattr(
            seeds_module,
            "_iter_seed_entries",
            lambda *paths: sample_payload,
        )
        monkeypatch.setattr(
            seeds_module,
            "_verse_bounds",
            lambda reference: (None, None),
        )
        monkeypatch.setattr(
            seeds_module,
            "_verse_range",
            lambda reference: None,
        )

        with Session(engine) as session:
            seed_contradiction_claims(session)
            value = session.execute(
                text(
                    "SELECT perspective FROM contradiction_seeds ORDER BY id LIMIT 1"
                )
            ).scalar_one()

        assert value == "skeptical"

        with engine.connect() as connection:
            result = connection.exec_driver_sql("PRAGMA table_info('contradiction_seeds')")
            rows = result.fetchall()
        assert any(row[1] == "perspective" for row in rows)
    finally:
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]
        for residual in db_path.parent.glob(f"{db_path.name}*"):
            residual.unlink(missing_ok=True)


def test_sqlite_startup_restores_missing_perspective_column(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "startup.db"

    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE contradiction_seeds (
                id TEXT PRIMARY KEY,
                osis_a TEXT NOT NULL,
                osis_b TEXT NOT NULL,
                summary TEXT,
                source TEXT,
                tags TEXT,
                weight REAL,
                created_at TEXT
            );
            """
        )

    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute("PRAGMA table_info('contradiction_seeds')")
        assert all(row[1] != "perspective" for row in cursor.fetchall())

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    database_module._engine = None  # type: ignore[attr-defined]
    database_module._SessionLocal = None  # type: ignore[attr-defined]

    def _lightweight_seed_reference_data(
        session: Session, *_, **__
    ) -> None:
        # Reuse the column repair logic while avoiding heavy dataset loading paths.
        seeds_module._repair_missing_perspective_columns(session)

    monkeypatch.setattr(seeds_module, "seed_reference_data", _lightweight_seed_reference_data)
    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.lifecycle.seed_reference_data",
        _lightweight_seed_reference_data,
    )

    try:
        with TestClient(app):
            pass

        engine = get_engine()
        with engine.connect() as connection:
            result = connection.exec_driver_sql("PRAGMA table_info('contradiction_seeds')")
            assert any(row[1] == "perspective" for row in result)
    finally:
        get_settings.cache_clear()
        engine = database_module._engine
        if engine is not None:
            engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]
        for residual in db_path.parent.glob(f"{db_path.name}*"):
            residual.unlink(missing_ok=True)
