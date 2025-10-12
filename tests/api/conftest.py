"""Shared test configuration for API-level tests."""
from __future__ import annotations

import os
os.environ.setdefault("SETTINGS_SECRET_KEY", "test-secret-key")
os.environ.setdefault("THEO_API_KEYS", '["pytest-default-key"]')
os.environ.setdefault("THEO_ALLOW_INSECURE_STARTUP", "1")

from pathlib import Path
import sys

import pytest
from fastapi import Request as FastAPIRequest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import inspect as sa_inspect

from theo.services.api.app.main import app
from theo.services.api.app.db import run_sql_migrations as migrations_module
from theo.application.facades import database as database_module
from theo.application.facades.database import Base, configure_engine, get_engine
from theo.services.api.app.security import require_principal

@pytest.fixture(autouse=True)
def _bypass_authentication(request: pytest.FixtureRequest):
    """Permit unauthenticated access for API tests unless explicitly disabled."""

    if request.node.get_closest_marker("no_auth_override"):
        yield
        return

    def _principal_override(fastapi_request: FastAPIRequest):
        principal = {"method": "override", "subject": "test"}
        fastapi_request.state.principal = principal
        return principal

    app.dependency_overrides[require_principal] = _principal_override
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_principal, None)


@pytest.fixture(autouse=True)
def _disable_migrations(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prevent database migrations from running in API tests."""

    if request.node.get_closest_marker("enable_migrations"):
        yield
        return

    original_run_sql_migrations = migrations_module.run_sql_migrations
    original_configure_engine = database_module.configure_engine

    def _needs_sqlite_perspective(engine) -> bool:
        if engine is None:
            return False
        dialect_name = getattr(engine.dialect, "name", None)
        if dialect_name != "sqlite":
            return False
        try:
            return not migrations_module._sqlite_has_column(  # type: ignore[attr-defined]
                engine, "contradiction_seeds", "perspective"
            )
        except Exception:
            try:
                inspector = sa_inspect(engine)
                columns = inspector.get_columns("contradiction_seeds")
            except Exception:
                return False
            return not any(column.get("name") == "perspective" for column in columns)

    def _apply_sqlite_perspective_sql(engine, migrations_path) -> list[str]:
        migration_dir = (
            Path(migrations_path)
            if migrations_path is not None
            else migrations_module.MIGRATIONS_PATH
        )
        migration_name = getattr(
            migrations_module,
            "_SQLITE_PERSPECTIVE_MIGRATION",
            "20250129_add_perspective_to_contradiction_seeds.sql",
        )
        migration_path = Path(migration_dir) / migration_name
        if not migration_path.exists():
            return []

        try:
            sql = migration_path.read_text(encoding="utf-8")
        except Exception:
            return []

        try:
            statements = migrations_module._split_sql_statements(sql)
        except Exception:
            return []

        applied = False
        try:
            with engine.begin() as connection:
                for statement in statements:
                    try:
                        if migrations_module._sqlite_add_column_exists(
                            connection, statement
                        ):
                            continue
                        connection.exec_driver_sql(statement)
                        applied = True
                    except Exception:
                        # If the targeted migration fails we fall back to the
                        # legacy behaviour and let the caller retry via the full
                        # migration runner.
                        return []
        except Exception:
            return []

        if not applied:
            return []

        try:
            recreated = migrations_module._sqlite_has_column(
                engine, "contradiction_seeds", "perspective"
            )
        except Exception:
            return []

        return [migration_path.name] if recreated else []

    def _ensure_sqlite_perspective(
        engine,
        *,
        migrations_path=None,
        force: bool = False,
    ) -> list[str]:
        if not _needs_sqlite_perspective(engine):
            return []

        try:
            Base.metadata.create_all(bind=engine)
        except Exception:
            # ``create_all`` may fail on partially initialised databases. We only
            # care about ensuring the contradiction seeds table exposes the
            # ``perspective`` column, so failures here are ignored and handled by
            # the migration attempts below.
            pass

        applied = _apply_sqlite_perspective_sql(engine, migrations_path)
        if applied:
            return applied

        try:
            return original_run_sql_migrations(
                engine=engine,
                migrations_path=migrations_path,
                force=force,
            )
        except Exception:
            # Defensive: the perspective backfill should never raise in tests, but
            # the sandboxed SQLite databases that back these fixtures occasionally
            # produce driver-level errors (for example when multiple connections
            # race to initialise pragmas). Falling back to the legacy behaviour
            # keeps the fixture resilient while still exercising the migration
            # path when possible.
            return []

    def _configure_engine_with_perspective(*args, **kwargs):
        engine = original_configure_engine(*args, **kwargs)
        _ensure_sqlite_perspective(engine)
        return engine

    existing_engine = getattr(database_module, "_engine", None)
    if existing_engine is not None:
        _ensure_sqlite_perspective(existing_engine)

    monkeypatch.setattr(database_module, "configure_engine", _configure_engine_with_perspective)
    monkeypatch.setattr(
        "theo.application.facades.database.configure_engine",
        _configure_engine_with_perspective,
    )
    globals()["configure_engine"] = _configure_engine_with_perspective

    engine = None
    try:
        engine = get_engine()
    except Exception:
        engine = None

    if engine is not None:
        _ensure_sqlite_perspective(engine)

    def _guarded_run_sql_migrations(
        engine=None,
        migrations_path=None,
        *,
        force: bool = False,
    ) -> list[str]:
        target_engine = engine or get_engine()
        if target_engine is None:
            return []
        applied = _ensure_sqlite_perspective(
            target_engine,
            migrations_path=migrations_path,
            force=force,
        )
        if applied:
            return applied
        return []

    monkeypatch.setattr(
        migrations_module,
        "run_sql_migrations",
        _guarded_run_sql_migrations,
    )
    monkeypatch.setattr(
        "theo.services.api.app.main.run_sql_migrations",
        _guarded_run_sql_migrations,
    )

    yield


@pytest.fixture()
def api_engine(tmp_path_factory: pytest.TempPathFactory):
    """Configure and tear down an isolated SQLite engine for API tests."""

    database_path = tmp_path_factory.mktemp("db") / "api.sqlite"
    configure_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(bind=get_engine())

    engine = get_engine()

    try:
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]

