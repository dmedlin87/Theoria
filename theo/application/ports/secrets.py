"""Ports for resolving secrets from external backends."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class SecretRetrievalError(RuntimeError):
    """Raised when a secret cannot be retrieved from the configured backend."""


@dataclass(slots=True)
class SecretRequest:
    """Describe a secret lookup request."""

    identifier: str
    field: str | None = None


class SecretsPort(Protocol):
    """Protocol implemented by secrets backends."""

    def get_secret(self, request: SecretRequest) -> str | None:
        """Resolve a secret value for the provided request."""


def build_secrets_adapter(backend: str, **kwargs: object) -> SecretsPort:
    """Instantiate a secrets adapter for the provided backend."""

    normalized = backend.strip().lower()
    if not normalized:
        raise ValueError("Backend name must be provided")
    if normalized == "vault":
        from theo.adapters.secrets.vault import VaultSecretsAdapter

        return VaultSecretsAdapter.from_config(**kwargs)
    if normalized == "aws":
        from theo.adapters.secrets.aws import AWSSecretsAdapter

        return AWSSecretsAdapter.from_config(**kwargs)
    raise ValueError(f"Unsupported secrets backend '{backend}'")
