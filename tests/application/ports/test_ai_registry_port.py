from __future__ import annotations

from typing import Any

import pytest

from theo.application.ports import ai_registry


class DummyCipher:
    def __init__(self, secrets: dict[str, str] | None = None) -> None:
        self._secrets = secrets or {}

    def decrypt(self, token: bytes) -> bytes:
        decoded = token.decode("utf-8")
        if decoded not in self._secrets:
            raise AssertionError(f"unexpected token: {decoded}")
        return self._secrets[decoded].encode("utf-8")

    def encrypt(self, value: bytes) -> bytes:  # pragma: no cover - not used directly
        return value


@pytest.fixture
def cipher(monkeypatch: pytest.MonkeyPatch) -> DummyCipher:
    instance = DummyCipher({"encrypted": "decrypted"})
    monkeypatch.setattr(ai_registry, "get_settings_cipher", lambda: instance)
    return instance


def test_registry_from_payload_decrypts_encrypted_config(cipher: DummyCipher) -> None:
    payload = {
        "models": [
            {
                "name": "primary",
                "provider": "openai",
                "model": "gpt-4",
                "config": {"api_key": {"__encrypted__": "encrypted"}},
            }
        ]
    }

    registry, migrated = ai_registry.registry_from_payload(payload)

    model = registry.get("primary")
    assert model.config["api_key"] == "decrypted"
    assert migrated is False


def test_registry_from_payload_marks_plaintext_for_migration(monkeypatch: pytest.MonkeyPatch) -> None:
    cipher = DummyCipher()
    monkeypatch.setattr(ai_registry, "get_settings_cipher", lambda: cipher)

    payload = {
        "models": [
            {
                "name": "primary",
                "provider": "openai",
                "model": "gpt-4",
                "config": {"api_key": "plaintext"},
            }
        ]
    }

    registry, migrated = ai_registry.registry_from_payload(payload)

    assert registry.get("primary").config["api_key"] == "plaintext"
    assert migrated is True


def test_registry_from_payload_bootstraps_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    class StubSettings:
        def __init__(self) -> None:
            self.llm_models: dict[str, Any] = {
                "bootstrap": {"provider": "anthropic", "model": "sonnet"}
            }
            self.llm_default_model = "bootstrap"
            self.openai_api_key = None
            self.openai_base_url = None

    settings = StubSettings()
    monkeypatch.setattr(ai_registry, "get_settings", lambda: settings)
    monkeypatch.setattr(ai_registry, "get_settings_cipher", lambda: None)

    registry, migrated = ai_registry.registry_from_payload(None)

    assert registry.get().name == "bootstrap"
    assert migrated is False
