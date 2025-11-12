"""Tests for the application secret migration facade."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from tests.api.core import reload_facade


@dataclass
class MemoryAppSetting:
    key: str
    value: Any


class MemorySession:
    def __init__(self, initial: list[MemoryAppSetting] | None = None) -> None:
        self.storage: dict[str, MemoryAppSetting] = {}
        for record in initial or []:
            self.storage[record.key] = record

    def get(self, _model: Any, key: str) -> MemoryAppSetting | None:
        return self.storage.get(key)

    def add(self, record: MemoryAppSetting) -> None:
        self.storage[record.key] = record

    def commit(self) -> None:  # pragma: no cover - unused but required by interface
        pass


class FakeCipher:
    def encrypt(self, payload: bytes) -> bytes:
        return f"enc:{payload.decode('utf-8')}".encode("utf-8")

    def decrypt(self, token: bytes) -> bytes:
        value = token.decode("utf-8")
        assert value.startswith("enc:")
        return value[len("enc:") :].encode("utf-8")


def test_migrate_secret_settings_encrypts_plaintext(monkeypatch: pytest.MonkeyPatch) -> None:
    store_module = reload_facade("theo.application.facades.settings_store")
    monkeypatch.setattr(store_module, "AppSetting", MemoryAppSetting)

    secret_module = reload_facade("theo.application.facades.secret_migration")
    monkeypatch.setattr(secret_module, "AppSetting", MemoryAppSetting)
    monkeypatch.setattr(secret_module, "save_setting", store_module.save_setting)

    cipher = FakeCipher()
    monkeypatch.setattr(store_module, "get_settings_cipher", lambda: cipher)
    monkeypatch.setattr(secret_module, "get_settings_cipher", lambda: cipher)

    monkeypatch.setattr(secret_module, "registry_from_payload", lambda payload: (payload or {}, []))

    captured_registries: list[Any] = []

    def _capture_registry(session: MemorySession, registry: Any) -> None:
        captured_registries.append(registry)
        store_module.save_setting(session, "llm", registry)

    secret_module.set_llm_registry_saver(_capture_registry)

    llm_key = f"{store_module.SETTINGS_NAMESPACE}:llm"
    provider_key = f"{store_module.SETTINGS_NAMESPACE}:ai_providers"
    session = MemorySession(
        [
            MemoryAppSetting(
                key=llm_key,
                value={"models": [{"name": "gpt", "config": {"api_key": "plaintext"}}]},
            ),
            MemoryAppSetting(
                key=provider_key,
                value={"openai": {"api_key": "secret"}},
            ),
        ]
    )

    migrated = secret_module.migrate_secret_settings(session)
    assert migrated == ["llm", "ai_providers"]
    assert captured_registries == [
        {"models": [{"name": "gpt", "config": {"api_key": "plaintext"}}]}
    ]
    assert "__encrypted__" in session.storage[provider_key].value

    secret_module.set_llm_registry_saver(lambda *_args, **_kwargs: None)
