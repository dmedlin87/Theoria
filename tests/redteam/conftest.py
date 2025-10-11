"""Shared fixtures for the red-team test suite."""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Generator
from pathlib import Path

import pytest

os.environ.setdefault("SETTINGS_SECRET_KEY", "test-secret-key")
os.environ.setdefault("THEO_AUTH_ALLOW_ANONYMOUS", "1")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="package", autouse=True)
def configure_redteam_environment(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[None, None, None]:
    """Provision a temporary database/storage layout for the suite."""

    db_path = tmp_path_factory.mktemp("redteam-db") / "test.db"
    storage_root = tmp_path_factory.mktemp("redteam-storage")

    env_overrides = {
        "DATABASE_URL": f"sqlite:///{db_path}",
        "STORAGE_ROOT": str(storage_root),
        "FIXTURES_ROOT": str(PROJECT_ROOT / "fixtures"),
        "THEO_AUTH_ALLOW_ANONYMOUS": "1",
    }
    original_env = {key: os.environ.get(key) for key in env_overrides}
    original_api_keys = os.environ.get("THEO_API_KEYS")

    for key, value in env_overrides.items():
        os.environ[key] = value

    # Guardrail suites expect anonymous access regardless of broader test
    # configuration. Other suites may have populated ``THEO_API_KEYS`` which
    # forces authentication even when ``THEO_AUTH_ALLOW_ANONYMOUS`` is set. Drop
    # API key configuration within this fixture so guardrail requests proceed
    # without credentials. The fixture is package-scoped so the override only
    # applies to tests within ``tests/redteam``.
    os.environ.pop("THEO_API_KEYS", None)

    from theo.services.api.app.core import settings as settings_module
    from theo.services.api.app.core.database import Base, configure_engine

    settings_module.get_settings.cache_clear()
    settings = settings_module.get_settings()
    setattr(settings_module, "settings", settings)

    engine = configure_engine(settings.database_url)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    try:
        yield
    finally:
        Base.metadata.drop_all(bind=engine)
        shutil.rmtree(storage_root, ignore_errors=True)
        if db_path.exists():
            db_path.unlink()

        for key, value in env_overrides.items():
            previous = original_env.get(key)
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous

        if original_api_keys is None:
            os.environ.pop("THEO_API_KEYS", None)
        else:
            os.environ["THEO_API_KEYS"] = original_api_keys

        settings_module.get_settings.cache_clear()
