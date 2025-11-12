"""Tests for the application runtime facade."""
from __future__ import annotations

import importlib

import pytest

from theo.application.facades import runtime as facades_runtime


def test_allow_insecure_startup_requires_non_production_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runtime facade should restrict insecure startup to dev environments."""

    module = importlib.reload(facades_runtime)
    module.allow_insecure_startup.cache_clear()

    monkeypatch.setenv("THEO_ALLOW_INSECURE_STARTUP", "true")
    monkeypatch.setenv("THEORIA_ENVIRONMENT", "development")
    assert module.allow_insecure_startup() is True

    module.allow_insecure_startup.cache_clear()
    monkeypatch.setenv("THEORIA_ENVIRONMENT", "production")
    with pytest.raises(RuntimeError):
        module.allow_insecure_startup()
