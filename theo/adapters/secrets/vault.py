"""HashiCorp Vault adapter."""
from __future__ import annotations

from typing import Any, Protocol

from theo.application.ports.secrets import SecretRequest, SecretRetrievalError, SecretsPort

try:  # pragma: no cover - optional dependency
    import hvac
except ImportError:  # pragma: no cover - dependency is optional
    hvac = None


class _VaultClient(Protocol):
    def read_secret_version(self, *, path: str, mount_point: str | None = None) -> dict[str, Any]:
        """Protocol describing the required Vault KV v2 client interface."""


class _VaultAdapterClient:
    """Small wrapper exposing a uniform interface over hvac's KV helpers."""

    def __init__(self, client: Any, *, mount_point: str | None = None) -> None:
        self._client = client
        self._mount_point = mount_point or "secret"

    def read_secret_version(
        self, *, path: str, mount_point: str | None = None
    ) -> dict[str, Any]:
        effective_mount = mount_point or self._mount_point
        return self._client.secrets.kv.v2.read_secret_version(
            path=path, mount_point=effective_mount
        )


class VaultSecretsAdapter(SecretsPort):
    """Resolve secrets stored in Vault's KV v2 engine."""

    def __init__(
        self,
        client: _VaultClient,
        *,
        mount_point: str | None = None,
        default_field: str | None = None,
    ) -> None:
        self._client = client
        self._mount_point = mount_point
        self._default_field = default_field

    @classmethod
    def from_config(
        cls,
        *,
        client: Any | None = None,
        url: str | None = None,
        token: str | None = None,
        namespace: str | None = None,
        mount_point: str | None = None,
        default_field: str | None = None,
        verify: bool | str | None = None,
    ) -> "VaultSecretsAdapter":
        if client is None:
            if hvac is None:
                raise RuntimeError(
                    "hvac must be installed to create a Vault secrets adapter"
                )
            if url is None or token is None:
                raise ValueError("Vault URL and token must be provided")
            client = hvac.Client(
                url=url, token=token, namespace=namespace, verify=verify
            )
            client = _VaultAdapterClient(client, mount_point=mount_point)
        return cls(
            client=client,
            mount_point=mount_point,
            default_field=default_field,
        )

    def get_secret(self, request: SecretRequest) -> str | None:
        try:
            response = self._client.read_secret_version(
                path=request.identifier, mount_point=self._mount_point
            )
        except Exception as exc:  # pragma: no cover - hvac raises HTTP errors
            raise SecretRetrievalError(str(exc)) from exc

        data = response.get("data") or {}
        if isinstance(data, dict) and "data" in data:
            data = data.get("data", {})

        if not isinstance(data, dict):
            raise SecretRetrievalError("Vault secret payload is malformed")

        field = request.field or self._default_field
        if field:
            if field not in data:
                raise SecretRetrievalError(
                    f"Field '{field}' not present in Vault secret"
                )
            value = data[field]
            return value if isinstance(value, str) else str(value)

        if len(data) == 1:
            (value,) = data.values()
            return value if isinstance(value, str) else str(value)

        raise SecretRetrievalError(
            "Secret field was not specified and payload contained multiple keys"
        )
