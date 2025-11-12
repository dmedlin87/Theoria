"""Tests for the application settings facade."""
from __future__ import annotations

import pytest

from tests.api.core import reload_facade


def test_get_settings_uses_environment_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The settings facade should load values from environment variables."""

    module = reload_facade("theo.application.facades.settings")
    module.get_settings.cache_clear()

    monkeypatch.setenv("THEO_CORS_ALLOWED_ORIGINS", "[\"https://example.com\"]")
    monkeypatch.setenv("THEO_STORAGE_ROOT", "./data")

    settings = module.get_settings()
    assert settings.cors_allowed_origins == ["https://example.com"]
    assert str(settings.storage_root) == "data"


def test_get_settings_cipher_uses_insecure_fallback_when_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When insecure startup is permitted, the facade should create a fallback cipher."""

    module = reload_facade("theo.application.facades.settings")
    module.get_settings.cache_clear()
    module.get_settings_secret.cache_clear()
    module.get_settings_cipher.cache_clear()

    monkeypatch.setattr(module, "allow_insecure_startup", lambda: True)

    class DummyFernet:
        def __init__(self, key: bytes) -> None:
            self.key = key

    monkeypatch.setattr(module, "Fernet", DummyFernet)

    cipher = module.get_settings_cipher()
    assert isinstance(cipher, DummyFernet)
