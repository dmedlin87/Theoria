"""Shared test configuration for API-level tests."""
from __future__ import annotations

import os
os.environ.setdefault("SETTINGS_SECRET_KEY", "test-secret-key")
os.environ.setdefault("THEO_API_KEYS", '["pytest-default-key"]')

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
from theo.services.api.app.core.database import get_engine
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

    engine = None
    try:
        engine = get_engine()
    except Exception:
        engine = None

    if _needs_sqlite_perspective(engine):
        try:
            original_run_sql_migrations(engine)
        except Exception:
            pass

    monkeypatch.setattr(migrations_module, "run_sql_migrations", lambda *_: [])
    monkeypatch.setattr(
        "theo.services.api.app.main.run_sql_migrations", lambda *_: []
    )

    yield

