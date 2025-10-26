"""Tests for the Vault secrets adapter."""
from __future__ import annotations

import pytest
from types import SimpleNamespace

from theo.adapters.secrets.vault import VaultSecretsAdapter
from theo.application.ports.secrets import SecretRequest, SecretRetrievalError


class DummyVaultClient:
    def __init__(self, response: dict[str, object] | Exception) -> None:
        self._response = response
        self.calls: list[tuple[str, str | None]] = []

    def read_secret_version(
        self, *, path: str, mount_point: str | None = None
    ) -> dict[str, object]:
        self.calls.append((path, mount_point))
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def test_vault_adapter_extracts_configured_field() -> None:
    payload = {"data": {"data": {"token": "value", "other": "ignored"}}}
    client = DummyVaultClient(payload)
    adapter = VaultSecretsAdapter(client=client, default_field="token")

    secret = adapter.get_secret(SecretRequest(identifier="settings/secret"))

    assert secret == "value"
    assert client.calls == [("settings/secret", None)]


def test_vault_adapter_requires_field_when_multiple_values() -> None:
    payload = {"data": {"data": {"alpha": "1", "beta": "2"}}}
    client = DummyVaultClient(payload)
    adapter = VaultSecretsAdapter(client=client)

    with pytest.raises(SecretRetrievalError):
        adapter.get_secret(SecretRequest(identifier="settings"))


def test_vault_adapter_surfaces_backend_errors() -> None:
    client = DummyVaultClient(RuntimeError("boom"))
    adapter = VaultSecretsAdapter(client=client)

    with pytest.raises(SecretRetrievalError) as excinfo:
        adapter.get_secret(SecretRequest(identifier="settings"))

    assert "boom" in str(excinfo.value)


def test_vault_adapter_detects_malformed_payload() -> None:
    client = DummyVaultClient({"data": "unexpected"})
    adapter = VaultSecretsAdapter(client=client)

    with pytest.raises(SecretRetrievalError):
        adapter.get_secret(SecretRequest(identifier="broken"))


def test_vault_adapter_from_config_requires_hvac(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("theo.adapters.secrets.vault.hvac", None)

    with pytest.raises(RuntimeError):
        VaultSecretsAdapter.from_config(url="http://vault", token="token")


def test_vault_adapter_from_config_with_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _Client:
        class secrets:  # noqa: N801 - mimic hvac attribute naming
            class kv:
                class v2:
                    @staticmethod
                    def read_secret_version(*, path: str, mount_point: str | None = None):
                        captured["path"] = path
                        captured["mount_point"] = mount_point
                        return {"data": {"data": {"token": "value"}}}

    monkeypatch.setattr("theo.adapters.secrets.vault.hvac", SimpleNamespace(Client=lambda **_: _Client()))

    adapter = VaultSecretsAdapter.from_config(
        url="http://vault",
        token="token",
        mount_point="kv",
        default_field="token",
    )

    secret = adapter.get_secret(SecretRequest(identifier="app/config"))

    assert secret == "value"
    assert captured["path"] == "app/config"
    assert captured["mount_point"] == "kv"
