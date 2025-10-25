"""Pytest fixtures for the Theo Engine API."""

from __future__ import annotations

import os
import shutil
import sys
import types
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi import Request as FastAPIRequest

os.environ.setdefault("SETTINGS_SECRET_KEY", "test-secret-key")
os.environ.setdefault("THEO_API_KEYS", "[\"pytest-default-key\"]")
os.environ.setdefault("THEO_ALLOW_INSECURE_STARTUP", "1")
os.environ.setdefault("THEORIA_ENVIRONMENT", "development")

_DISCOVERIES_MODULE = types.ModuleType("theo.services.api.app.discoveries")
_DISCOVERY_TASKS_MODULE = types.ModuleType("theo.services.api.app.discoveries.tasks")


def _noop_schedule_discovery_refresh(*_: object, **__: object) -> None:
    return None


_DISCOVERY_TASKS_MODULE.schedule_discovery_refresh = _noop_schedule_discovery_refresh  # type: ignore[attr-defined]


class _DiscoveryServiceStub:
    def __init__(self, *_: object, **__: object) -> None:
        raise RuntimeError("Discovery service is not available in this test environment")


_DISCOVERIES_MODULE.DiscoveryService = _DiscoveryServiceStub  # type: ignore[attr-defined]
_DISCOVERIES_MODULE.tasks = _DISCOVERY_TASKS_MODULE  # type: ignore[attr-defined]
sys.modules.setdefault("theo.services.api.app.discoveries", _DISCOVERIES_MODULE)
sys.modules.setdefault("theo.services.api.app.discoveries.tasks", _DISCOVERY_TASKS_MODULE)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.main import app
from theo.services.api.app.db.run_sql_migrations import run_sql_migrations
from theo.services.api.app.adapters.security import require_principal


def _use_pgvector_backend(request: pytest.FixtureRequest) -> bool:
    try:
        option = request.config.getoption("use_pgvector")
    except (AttributeError, ValueError):
        option = False
    return bool(option or os.environ.get("PYTEST_USE_PGVECTOR"))


@pytest.fixture(scope="session", autouse=True)
def configure_test_environment(
    tmp_path_factory: pytest.TempPathFactory,
    request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    """Configure database and storage paths for tests."""

    use_pgvector = _use_pgvector_backend(request)
    db_path = tmp_path_factory.mktemp("db") / "test.db"
    storage_root = tmp_path_factory.mktemp("storage")

    if use_pgvector:
        database_url: str = request.getfixturevalue("pgvector_migrated_database_url")
    else:
        database_url = f"sqlite:///{db_path}"

    env_overrides = {
        "DATABASE_URL": database_url,
        "STORAGE_ROOT": str(storage_root),
        "FIXTURES_ROOT": str(PROJECT_ROOT / "fixtures"),
        "INGEST_URL_BLOCK_PRIVATE_NETWORKS": "false",
        "INGEST_URL_BLOCKED_IP_NETWORKS": "[]",
        "INGEST_URL_BLOCKED_HOSTS": "[]",
        "INGEST_URL_ALLOWED_HOSTS": "[]",
    }
    original_env = {key: os.environ.get(key) for key in env_overrides}

    for key, value in env_overrides.items():
        os.environ[key] = value

    from theo.application.facades import settings as settings_module
    from theo.application.facades.database import Base, configure_engine

    settings_module.get_settings.cache_clear()
    settings = settings_module.get_settings()
    engine = configure_engine(settings.database_url)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    run_sql_migrations(engine)

    try:
        yield
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        shutil.rmtree(storage_root, ignore_errors=True)
        if not use_pgvector and db_path.exists():
            db_path.unlink()
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.fixture(autouse=True)
def bypass_authentication(request: pytest.FixtureRequest) -> Generator[None, None, None]:
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





