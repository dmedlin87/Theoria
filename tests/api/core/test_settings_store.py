"""Tests for the application settings store facade."""
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
    def __init__(self) -> None:
        self.storage: dict[str, MemoryAppSetting] = {}
        self.commits = 0

    def get(self, _model: Any, key: str) -> MemoryAppSetting | None:
        return self.storage.get(key)

    def add(self, record: MemoryAppSetting) -> None:
        self.storage[record.key] = record

    def commit(self) -> None:
        self.commits += 1


class FakeCipher:
    def __init__(self) -> None:
        self.encrypted: list[str] = []

    def encrypt(self, payload: bytes) -> bytes:
        token = f"enc:{payload.decode('utf-8')}"
        self.encrypted.append(token)
        return token.encode("utf-8")

    def decrypt(self, token: bytes) -> bytes:
        value = token.decode("utf-8")
        assert value.startswith("enc:")
        return value[len("enc:") :].encode("utf-8")


def _load_store(monkeypatch: pytest.MonkeyPatch):
    module = reload_facade("theo.application.facades.settings_store")
    monkeypatch.setattr(module, "AppSetting", MemoryAppSetting)
    return module


def test_save_and_load_setting_round_trips_encrypted_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_store(monkeypatch)
    cipher = FakeCipher()
    monkeypatch.setattr(module, "get_settings_cipher", lambda: cipher)

    session = MemorySession()
    module.save_setting(session, "provider.credentials", {"api_key": "secret"})

    qualified = f"{module.SETTINGS_NAMESPACE}:provider.credentials"
    record = session.storage[qualified]
    assert "__encrypted__" in record.value

    loaded = module.load_setting(session, "provider.credentials")
    assert loaded == {"api_key": "secret"}
    required = module.require_setting(session, "provider.credentials")
    assert required == {"api_key": "secret"}
    assert session.commits == 1


def test_save_setting_requires_cipher_for_sensitive_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_store(monkeypatch)
    monkeypatch.setattr(module, "get_settings_cipher", lambda: None)

    session = MemorySession()
    with pytest.raises(RuntimeError):
        module.save_setting(session, "provider.credentials", {"api_key": "secret"})
