"""Shared test configuration for API-level tests."""
from __future__ import annotations

import os
import shutil
os.environ.setdefault("SETTINGS_SECRET_KEY", "test-secret-key")
os.environ.setdefault("THEO_API_KEYS", '["pytest-default-key"]')
os.environ.setdefault("THEO_ALLOW_INSECURE_STARTUP", "1")
os.environ.setdefault("THEORIA_ENVIRONMENT", "development")

from pathlib import Path
import sys

import pytest
from fastapi import Request as FastAPIRequest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
    """Prevent migrations from running during API startup.

    Migrations are already applied by the integration_database_url fixture,
    so we don't need to run them again during FastAPI app lifespan startup.
    """

    if request.node.get_closest_marker("enable_migrations"):
        yield
        return

    # Replace run_sql_migrations with a no-op since migrations were already
    # applied by the fixture that created the test database
    def _noop_run_sql_migrations(
        engine=None,
        migrations_path=None,
        *,
        force: bool = False,
    ) -> list[str]:
        return []

    monkeypatch.setattr(
        migrations_module,
        "run_sql_migrations",
        _noop_run_sql_migrations,
    )
    monkeypatch.setattr(
        "theo.services.api.app.main.run_sql_migrations",
        _noop_run_sql_migrations,
    )

    yield


@pytest.fixture(scope="session", autouse=True)
def _skip_heavy_startup() -> None:
    monkeypatch = pytest.MonkeyPatch()
    """Disable expensive FastAPI lifespan setup steps for API tests."""

    from sqlalchemy import text as _sql_text
    from theo.services.api.app.db import seeds as _seeds_module

    original_seed_reference_data = _seeds_module.seed_reference_data

    def _maybe_seed_reference_data(session) -> None:
        """Invoke the real seeders when the database still needs backfilling."""

        needs_seeding = True
        try:
            bind = session.get_bind()
            if bind is not None:
                try:
                    perspective_present = bool(
                        session.execute(
                            _sql_text(
                                "SELECT 1 FROM pragma_table_info('contradiction_seeds') "
                                "WHERE name = 'perspective'"
                            )
                        ).first()
                    )
                except Exception:
                    perspective_present = False
                if perspective_present:
                    try:
                        has_rows = bool(
                            session.execute(
                                _sql_text(
                                    "SELECT 1 FROM contradiction_seeds LIMIT 1"
                                )
                            ).first()
                        )
                    except Exception:
                        has_rows = False
                    needs_seeding = not has_rows
                else:
                    needs_seeding = True
        except Exception:
            needs_seeding = True

        if needs_seeding:
            original_seed_reference_data(session)

    monkeypatch.setattr(
        "theo.services.api.app.main.seed_reference_data",
        _maybe_seed_reference_data,
        raising=False,
    )
    monkeypatch.setattr(
        "theo.services.api.app.main.start_discovery_scheduler",
        lambda: None,
        raising=False,
    )
    monkeypatch.setattr(
        "theo.services.api.app.main.stop_discovery_scheduler",
        lambda: None,
        raising=False,
    )

    try:
        yield
    finally:
        monkeypatch.undo()


@pytest.fixture(scope="session")
def _api_engine_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Materialise a migrated SQLite database once per test session."""
    from theo.services.api.app.db.run_sql_migrations import run_sql_migrations

    template_dir = tmp_path_factory.mktemp("api-engine-template")
    template_path = template_dir / "api.sqlite"
    engine = create_engine(f"sqlite:///{template_path}", future=True)
    try:
        Base.metadata.create_all(bind=engine)
        run_sql_migrations(engine)
    finally:
        engine.dispose()
    return template_path


@pytest.fixture()
def api_engine(
    tmp_path_factory: pytest.TempPathFactory,
    _api_engine_template: Path,
):
    """Provide an isolated SQLite engine for API tests with pre-applied migrations."""
    database_path = tmp_path_factory.mktemp("db") / "api.sqlite"
    # Clone the pre-migrated template so each test starts from the same baseline.
    shutil.copy2(_api_engine_template, database_path)
    configure_engine(f"sqlite:///{database_path}")

    engine = get_engine()

    try:
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]


@pytest.fixture()
def api_test_client(api_engine) -> TestClient:
    """Yield a ``TestClient`` bound to an isolated, migrated database."""

    with TestClient(app) as client:
        yield client

