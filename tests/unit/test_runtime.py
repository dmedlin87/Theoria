"""Tests for runtime startup guards."""

from __future__ import annotations

import pytest

from theo.application.facades import runtime


@pytest.fixture(autouse=True)
def clear_runtime_cache() -> None:
    """Ensure cached runtime checks are reset between tests."""

    runtime.allow_insecure_startup.cache_clear()
    yield
    runtime.allow_insecure_startup.cache_clear()


def test_allow_insecure_startup_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the override flag, insecure startup is not permitted."""

    monkeypatch.delenv("THEO_ALLOW_INSECURE_STARTUP", raising=False)
    monkeypatch.setenv("THEORIA_ENVIRONMENT", "development")

    assert runtime.allow_insecure_startup() is False


def test_allow_insecure_startup_allowed_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting the override works when environment is development."""

    monkeypatch.setenv("THEO_ALLOW_INSECURE_STARTUP", "1")
    monkeypatch.setenv("THEORIA_ENVIRONMENT", "development")

    assert runtime.allow_insecure_startup() is True


def test_allow_insecure_startup_rejected_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production environments cannot enable the override."""

    monkeypatch.setenv("THEO_ALLOW_INSECURE_STARTUP", "true")
    monkeypatch.setenv("THEORIA_ENVIRONMENT", "production")

    with pytest.raises(RuntimeError):
        runtime.allow_insecure_startup()
