from __future__ import annotations

"""Targeted tests for API authentication helpers."""

from collections.abc import Generator

import jwt
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from theo.application.facades import settings as settings_module
from theo.services.api.app.adapters.security import require_principal


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Generator[None, None, None]:
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


def _make_request() -> Request:
    return Request({"type": "http", "headers": []})


def _refresh_settings() -> None:
    settings_module.get_settings.cache_clear()


def test_require_principal_allows_anonymous_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THEO_API_KEYS", "[]")
    monkeypatch.setenv("THEO_AUTH_JWT_SECRET", "")
    monkeypatch.setenv("THEO_AUTH_ALLOW_ANONYMOUS", "true")
    _refresh_settings()

    request = _make_request()

    principal = require_principal(request, authorization=None, api_key_header=None)

    assert principal["method"] == "anonymous"
    assert request.state.principal == principal


def test_require_principal_with_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    api_key = "test-api-key"
    monkeypatch.setenv("THEO_API_KEYS", f'["{api_key}"]')
    monkeypatch.setenv("THEO_AUTH_ALLOW_ANONYMOUS", "false")
    monkeypatch.setenv("THEO_AUTH_JWT_SECRET", "")
    _refresh_settings()

    request = _make_request()

    principal = require_principal(request, authorization=None, api_key_header=api_key)

    assert principal["method"] == "api_key"
    assert principal["subject"] == api_key
    assert request.state.principal == principal


def test_require_principal_with_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "jwt-secret"
    monkeypatch.setenv("THEO_API_KEYS", "[]")
    monkeypatch.setenv("THEO_AUTH_JWT_SECRET", secret)
    monkeypatch.setenv("THEO_AUTH_ALLOW_ANONYMOUS", "false")
    _refresh_settings()

    token = jwt.encode({"sub": "user-123", "scopes": ["read"]}, secret, algorithm="HS256")

    request = _make_request()

    principal = require_principal(
        request, authorization=f"Bearer {token}", api_key_header=None
    )

    assert principal["method"] == "jwt"
    assert principal["subject"] == "user-123"
    assert principal["scopes"] == ["read"]
    assert request.state.principal == principal


def test_require_principal_raises_when_auth_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THEO_API_KEYS", "[]")
    monkeypatch.setenv("THEO_AUTH_JWT_SECRET", "")
    monkeypatch.setenv("THEO_AUTH_ALLOW_ANONYMOUS", "false")
    _refresh_settings()

    request = _make_request()

    with pytest.raises(HTTPException) as excinfo:
        require_principal(request, authorization=None, api_key_header=None)

    assert excinfo.value.status_code == 403
    assert "Authentication is not configured" in excinfo.value.detail
