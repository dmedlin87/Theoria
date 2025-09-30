"""Pytest fixtures for the Theo Engine API."""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi import Request as FastAPIRequest

os.environ.setdefault("SETTINGS_SECRET_KEY", "test-secret-key")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.main import app
from theo.services.api.app.security import require_principal


@pytest.fixture(scope="session", autouse=True)
def configure_test_environment(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[None, None, None]:
    """Configure database and storage paths for tests."""

    db_path = tmp_path_factory.mktemp("db") / "test.db"
    storage_root = tmp_path_factory.mktemp("storage")

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["STORAGE_ROOT"] = str(storage_root)
    os.environ["FIXTURES_ROOT"] = str(PROJECT_ROOT / "fixtures")
    os.environ["THEO_AUTH_ALLOW_ANONYMOUS"] = "1"

    from theo.services.api.app.core import settings as settings_module
    from theo.services.api.app.core.database import Base, configure_engine

    settings_module.get_settings.cache_clear()
    settings = settings_module.get_settings()
    engine = configure_engine(settings.database_url)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    yield

    Base.metadata.drop_all(bind=engine)
    shutil.rmtree(storage_root, ignore_errors=True)
    if db_path.exists():
        db_path.unlink()


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
