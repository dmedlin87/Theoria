from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from theo.services.api.app import main as main_module


def test_enforce_authentication_requires_credentials(monkeypatch):
    settings = SimpleNamespace(
        api_keys=[],
        auth_allow_anonymous=False,
        has_auth_jwt_credentials=lambda: False,
    )
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    monkeypatch.setattr(main_module, "allow_insecure_startup", lambda: False)

    with pytest.raises(RuntimeError):
        main_module._enforce_authentication_requirements()


def test_enforce_authentication_allows_insecure_override(monkeypatch):
    settings = SimpleNamespace(
        api_keys=[],
        auth_allow_anonymous=False,
        has_auth_jwt_credentials=lambda: False,
    )
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    monkeypatch.setattr(main_module, "allow_insecure_startup", lambda: True)

    main_module._enforce_authentication_requirements()


def test_enforce_authentication_blocks_anonymous_without_insecure(monkeypatch):
    settings = SimpleNamespace(
        api_keys=[],
        auth_allow_anonymous=True,
        has_auth_jwt_credentials=lambda: False,
    )
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    monkeypatch.setattr(main_module, "allow_insecure_startup", lambda: False)

    with pytest.raises(RuntimeError):
        main_module._enforce_authentication_requirements()


def test_enforce_secret_requirements(monkeypatch):
    monkeypatch.setattr(main_module, "get_settings_secret", lambda: None)
    monkeypatch.setattr(main_module, "allow_insecure_startup", lambda: False)

    with pytest.raises(RuntimeError):
        main_module._enforce_secret_requirements()


def test_enforce_secret_requirements_allows_insecure(monkeypatch):
    monkeypatch.setattr(main_module, "get_settings_secret", lambda: None)
    monkeypatch.setattr(main_module, "allow_insecure_startup", lambda: True)

    main_module._enforce_secret_requirements()


def test_enforce_secret_requirements_with_secret(monkeypatch):
    monkeypatch.setattr(main_module, "get_settings_secret", lambda: "secret")
    monkeypatch.setattr(main_module, "allow_insecure_startup", lambda: False)

    main_module._enforce_secret_requirements()


def test_configure_cors_adds_middleware():
    app = FastAPI()
    settings = SimpleNamespace(cors_allowed_origins=["https://example.com"])

    main_module._configure_cors(app, settings)

    assert any(m.cls is CORSMiddleware for m in app.user_middleware)


def test_attach_trace_headers_does_not_override_existing():
    response = Response()
    response.headers["X-Existing"] = "value"

    updated = main_module._attach_trace_headers(
        response,
        {"X-Trace": "abc123", "X-Existing": "new"},
    )

    assert updated.headers["X-Trace"] == "abc123"
    assert updated.headers["X-Existing"] == "value"
