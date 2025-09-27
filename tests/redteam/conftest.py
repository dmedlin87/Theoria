"""Shared fixtures for the red-team test suite."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session", autouse=True)
def configure_redteam_environment(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Provision a temporary database/storage layout for the suite."""

    db_path = tmp_path_factory.mktemp("redteam-db") / "test.db"
    storage_root = tmp_path_factory.mktemp("redteam-storage")

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["STORAGE_ROOT"] = str(storage_root)
    os.environ["FIXTURES_ROOT"] = str(PROJECT_ROOT / "fixtures")

    from theo.services.api.app.core import settings as settings_module
    from theo.services.api.app.core.database import Base, configure_engine

    settings_module.get_settings.cache_clear()
    settings = settings_module.get_settings()
    settings_module.settings = settings

    engine = configure_engine(settings.database_url)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    yield

    Base.metadata.drop_all(bind=engine)
    shutil.rmtree(storage_root, ignore_errors=True)
    if db_path.exists():
        db_path.unlink()
