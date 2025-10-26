"""Tests for the AWS Secrets Manager adapter."""
from __future__ import annotations

import base64

import pytest

from theo.adapters.secrets.aws import AWSSecretsAdapter
from theo.application.ports.secrets import SecretRequest, SecretRetrievalError


class DummyAWSClient:
    def __init__(self, response: dict[str, object] | Exception) -> None:
        self._response = response
        self.calls: list[str] = []

    def get_secret_value(self, *, SecretId: str) -> dict[str, object]:
        self.calls.append(SecretId)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def test_aws_adapter_returns_secret_string() -> None:
    client = DummyAWSClient({"SecretString": "plain-secret"})
    adapter = AWSSecretsAdapter(client=client)

    secret = adapter.get_secret(SecretRequest(identifier="app"))

    assert secret == "plain-secret"
    assert client.calls == ["app"]


def test_aws_adapter_extracts_json_field() -> None:
    response = {"SecretString": "{\"token\": \"value\", \"other\": 1}"}
    client = DummyAWSClient(response)
    adapter = AWSSecretsAdapter(client=client, default_field="token")

    secret = adapter.get_secret(SecretRequest(identifier="app"))

    assert secret == "value"


def test_aws_adapter_decodes_binary_payload() -> None:
    encoded = base64.b64encode(b"payload").decode("ascii")
    client = DummyAWSClient({"SecretBinary": encoded})
    adapter = AWSSecretsAdapter(client=client)

    secret = adapter.get_secret(SecretRequest(identifier="binary"))

    assert secret == "payload"


def test_aws_adapter_raises_when_field_missing() -> None:
    response = {"SecretString": "{\"token\": \"value\"}"}
    client = DummyAWSClient(response)
    adapter = AWSSecretsAdapter(client=client, default_field="missing")

    with pytest.raises(SecretRetrievalError):
        adapter.get_secret(SecretRequest(identifier="app"))


def test_aws_adapter_surfaces_backend_errors() -> None:
    client = DummyAWSClient(RuntimeError("error"))
    adapter = AWSSecretsAdapter(client=client)

    with pytest.raises(SecretRetrievalError) as excinfo:
        adapter.get_secret(SecretRequest(identifier="app"))

    assert "error" in str(excinfo.value)


def test_aws_adapter_reports_invalid_json_when_extracting_field() -> None:
    client = DummyAWSClient({"SecretString": "not-json"})
    adapter = AWSSecretsAdapter(client=client, default_field="token")

    with pytest.raises(SecretRetrievalError):
        adapter.get_secret(SecretRequest(identifier="bad"))


def test_aws_adapter_from_config_requires_boto3(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("theo.adapters.secrets.aws.boto3", None)

    with pytest.raises(RuntimeError):
        AWSSecretsAdapter.from_config(profile_name="default")


def test_aws_adapter_from_config_uses_provided_client(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _Client:
        def get_secret_value(self, *, SecretId: str) -> dict[str, object]:
            captured["secret"] = SecretId
            return {"SecretString": "value"}

    adapter = AWSSecretsAdapter.from_config(client=_Client(), default_field=None)

    secret = adapter.get_secret(SecretRequest(identifier="custom"))

    assert secret == "value"
    assert captured["secret"] == "custom"
