from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from theo.services.api.app.adapters import security as security_adapter


class StubSettings(SimpleNamespace):
    api_keys: list[str] | None = None
    auth_allow_anonymous: bool = False
    auth_jwt_algorithms: list[str] | None = None
    auth_jwt_secret: str | None = None
    auth_jwt_audience: str | None = None
    auth_jwt_issuer: str | None = None

    def has_auth_jwt_credentials(self) -> bool:  # pragma: no cover - helper
        return bool(self.auth_jwt_secret)

    def load_auth_jwt_public_key(self) -> str | None:  # pragma: no cover - helper
        return None


def _build_request() -> Request:
    scope = {"type": "http", "headers": [], "method": "GET", "path": "/"}
    return Request(scope)


def _patch_settings(monkeypatch, settings: StubSettings) -> None:
    def fake_get_settings() -> StubSettings:
        return settings

    fake_get_settings.cache_clear = lambda: None  # type: ignore[attr-defined]
    monkeypatch.setattr(security_adapter, "get_settings", fake_get_settings)


def test_fastapi_resolver_accepts_api_key(monkeypatch):
    settings = StubSettings(api_keys=["secret-key"], auth_allow_anonymous=False)
    _patch_settings(monkeypatch, settings)

    resolver = security_adapter.FastAPIPrincipalResolver()
    principal = asyncio.run(
        resolver.resolve(
            request=_build_request(),
            authorization=None,
            api_key_header="secret-key",
        )
    )

    assert principal["method"] == "api_key"
    assert principal["subject"] == "secret-key"


def test_fastapi_resolver_allows_anonymous_when_configured(monkeypatch):
    settings = StubSettings(api_keys=None, auth_allow_anonymous=True)
    _patch_settings(monkeypatch, settings)

    resolver = security_adapter.FastAPIPrincipalResolver()
    principal = asyncio.run(
        resolver.resolve(
            request=_build_request(),
            authorization=None,
            api_key_header=None,
        )
    )

    assert principal["method"] == "anonymous"
    assert principal["subject"] is None


def test_fastapi_resolver_rejects_invalid_api_key(monkeypatch):
    settings = StubSettings(api_keys=["expected"], auth_allow_anonymous=False)
    _patch_settings(monkeypatch, settings)

    resolver = security_adapter.FastAPIPrincipalResolver()

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            resolver.resolve(
                request=_build_request(),
                authorization=None,
                api_key_header="wrong",
            )
        )

    assert error.value.status_code == 403
