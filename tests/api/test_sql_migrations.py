from __future__ import annotations

from pathlib import Path

import importlib

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from theo.services.api.app.core.database import Base, configure_engine, get_engine
from theo.services.api.app.db.models import AppSetting
from theo.services.api.app.main import app


@pytest.mark.enable_migrations
@pytest.mark.usefixtures("_bypass_authentication")
def test_sql_migrations_run_on_startup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "app.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

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

    configure_engine("sqlite://")


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
