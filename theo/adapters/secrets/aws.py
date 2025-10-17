"""AWS Secrets Manager adapter."""
from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from typing import Any, Protocol

from theo.application.ports.secrets import SecretRequest, SecretRetrievalError, SecretsPort

try:  # pragma: no cover - optional dependency
    import boto3
except ImportError:  # pragma: no cover - dependency is optional
    boto3 = None


class _AWSClient(Protocol):
    def get_secret_value(self, *, SecretId: str) -> dict[str, Any]:
        """Protocol describing the boto3 Secrets Manager client."""


class AWSSecretsAdapter(SecretsPort):
    """Resolve secrets via AWS Secrets Manager."""

    def __init__(self, client: _AWSClient, *, default_field: str | None = None) -> None:
        self._client = client
        self._default_field = default_field

    @classmethod
    def from_config(
        cls,
        *,
        client: _AWSClient | None = None,
        profile_name: str | None = None,
        region_name: str | None = None,
        default_field: str | None = None,
    ) -> "AWSSecretsAdapter":
        if client is None:
            if boto3 is None:
                raise RuntimeError(
                    "boto3 must be installed to create an AWS secrets adapter"
                )
            session = boto3.session.Session(
                profile_name=profile_name, region_name=region_name
            )
            client = session.client("secretsmanager")
        return cls(client=client, default_field=default_field)

    def get_secret(self, request: SecretRequest) -> str | None:
        try:
            response = self._client.get_secret_value(SecretId=request.identifier)
        except Exception as exc:  # pragma: no cover - boto3 raises service exceptions
            raise SecretRetrievalError(str(exc)) from exc

        if "SecretString" in response and response["SecretString"] is not None:
            secret_string = response["SecretString"]
            field = request.field or self._default_field
            if field:
                try:
                    parsed = json.loads(secret_string)
                except (json.JSONDecodeError, TypeError) as exc:
                    raise SecretRetrievalError(
                        "SecretString is not valid JSON for field extraction"
                    ) from exc
                if not isinstance(parsed, Mapping):
                    raise SecretRetrievalError(
                        "SecretString JSON payload must be an object for field extraction"
                    )
                value = parsed.get(field)
                if value is None:
                    raise SecretRetrievalError(
                        f"Field '{field}' not present in AWS secret"
                    )
                return value if isinstance(value, str) else str(value)
            if isinstance(secret_string, str):
                return secret_string
            return str(secret_string)

        if "SecretBinary" in response and response["SecretBinary"] is not None:
            try:
                decoded = base64.b64decode(response["SecretBinary"])
            except (TypeError, ValueError) as exc:
                raise SecretRetrievalError("Unable to decode binary secret payload (base64 decoding failed)") from exc
            try:
                return decoded.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise SecretRetrievalError("Unable to decode binary secret payload (UTF-8 decoding failed)") from exc
            except UnicodeDecodeError as exc:
                raise SecretRetrievalError("Unable to decode binary secret payload as UTF-8") from exc
        raise SecretRetrievalError("Secret value not present in AWS response")
