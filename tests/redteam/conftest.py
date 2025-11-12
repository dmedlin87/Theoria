"""Shared fixtures for the red-team test suite."""

from __future__ import annotations

import contextlib
import os
import shutil
import sys
import types
from collections.abc import Generator
from pathlib import Path

import pytest

os.environ.setdefault("SETTINGS_SECRET_KEY", "test-secret-key")
os.environ.setdefault("THEO_AUTH_ALLOW_ANONYMOUS", "1")
os.environ.setdefault("THEO_ALLOW_INSECURE_STARTUP", "1")
os.environ.setdefault("THEORIA_ENVIRONMENT", "development")


@pytest.fixture(autouse=True)
def ensure_settings_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guarantee ``SETTINGS_SECRET_KEY`` is present for every test."""

    monkeypatch.setenv("SETTINGS_SECRET_KEY", "test-secret-key")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.api.conftest import _register_sklearn_stubs

_register_sklearn_stubs()


@pytest.fixture(scope="session", autouse=True)
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
    # forces authentication even when ``THEO_AUTH_ALLOW_ANONYMOUS`` is set.  Drop
    # API key configuration within this fixture so guardrail requests proceed
    # without credentials.
    os.environ.pop("THEO_API_KEYS", None)

    from theo.application.facades import settings as settings_module
    from theo.application.facades.database import Base, configure_engine

    settings_module.get_settings.cache_clear()
    settings = settings_module.get_settings()
    setattr(settings_module, "settings", settings)

    engine = configure_engine(settings.database_url)
    Base.metadata.create_all(bind=engine)

    try:
        yield
    finally:
        engine.dispose()
        shutil.rmtree(storage_root, ignore_errors=True)
        if db_path.exists():
            db_path.unlink()

        for key, _value in env_overrides.items():
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


@pytest.fixture(scope="session", autouse=True)
def _speed_up_redteam_startup() -> Generator[None, None, None]:
    monkeypatch = pytest.MonkeyPatch()

    def _noop_run_sql_migrations(
        engine=None,
        migrations_path=None,
        *,
        force: bool = False,
    ) -> list[str]:
        return []

    def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "theo.infrastructure.api.app.bootstrap.lifecycle.run_sql_migrations",
        _noop_run_sql_migrations,
    )
    monkeypatch.setattr(
        "theo.infrastructure.api.app.db.run_sql_migrations.run_sql_migrations",
        _noop_run_sql_migrations,
    )
    monkeypatch.setattr(
        "theo.infrastructure.api.app.bootstrap.lifecycle.seed_reference_data",
        _noop,
    )
    monkeypatch.setattr(
        "theo.infrastructure.api.app.db.seeds.seed_reference_data",
        _noop,
    )
    monkeypatch.setattr(
        "theo.infrastructure.api.app.workers.discovery_scheduler.start_discovery_scheduler",
        _noop,
        raising=False,
    )
    monkeypatch.setattr(
        "theo.infrastructure.api.app.workers.discovery_scheduler.stop_discovery_scheduler",
        _noop,
        raising=False,
    )

    try:
        yield
    finally:
        monkeypatch.undo()


@pytest.fixture(scope="session", autouse=True)
def _stub_redteam_integrations() -> Generator[None, None, None]:
    """Provide deterministic implementations for external integrations."""

    monkeypatch = pytest.MonkeyPatch()

    def _instrument_stub(*_args, **_kwargs):
        @contextlib.contextmanager
        def _manager():
            yield types.SimpleNamespace(set_attribute=lambda *a, **kw: None)

        return _manager()

    monkeypatch.setattr(
        "theo.application.facades.telemetry.instrument_workflow",
        _instrument_stub,
        raising=False,
    )
    monkeypatch.setattr(
        "theo.application.facades.telemetry.set_span_attribute",
        lambda *_a, **_kw: None,
        raising=False,
    )
    monkeypatch.setattr(
        "theo.infrastructure.api.app.ai.trails._compute_input_hash",
        lambda input_payload, tool, action: str(
            (tool or "", action or "", repr(input_payload))
        ),
        raising=False,
    )
    monkeypatch.setattr(
        "theo.infrastructure.api.app.ai.rag.guardrail_helpers.ensure_completion_safe",
        lambda *_a, **_kw: None,
        raising=False,
    )
    monkeypatch.setattr(
        "theo.infrastructure.api.app.ai.rag.chat.ensure_completion_safe",
        lambda *_a, **_kw: None,
        raising=False,
    )
    monkeypatch.setattr(
        "theo.infrastructure.api.app.ai.rag.guardrail_helpers.validate_model_completion",
        lambda completion, citations: {
            "status": "ok",
            "completion": completion,
            "citations": list(citations),
        },
        raising=False,
    )
    monkeypatch.setattr(
        "theo.infrastructure.api.app.ai.rag.chat.validate_model_completion",
        lambda completion, citations: {
            "status": "ok",
            "completion": completion,
            "citations": list(citations),
        },
        raising=False,
    )

    try:
        yield
    finally:
        monkeypatch.undo()
