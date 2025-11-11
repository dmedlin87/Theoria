"""Unit tests for the API bootstrap factory."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

from fastapi import FastAPI

if "FlagEmbedding" not in sys.modules:
    flag_module = ModuleType("FlagEmbedding")

    class _StubFlagModel:  # pragma: no cover - simple test double
        def __init__(self, *args, **kwargs) -> None:  # noqa: D401 - simple stub
            pass

        def encode(self, texts):
            return [[] for _ in texts]

    flag_module.FlagModel = _StubFlagModel  # type: ignore[attr-defined]
    sys.modules["FlagEmbedding"] = flag_module

from theo.infrastructure.api.app.bootstrap import app_factory
from theo.infrastructure.api.app.bootstrap.lifecycle import lifespan as bootstrap_lifespan


class DummySettings:
    auth_allow_anonymous = False
    api_keys = ["dummy"]
    cors_allowed_origins = ["https://example.test"]

    def has_auth_jwt_credentials(self) -> bool:
        return False


def test_create_app_uses_provided_settings(monkeypatch):
    calls: dict[str, object] = {}

    def fail_get_settings():
        raise AssertionError("should not call get_settings when settings provided")

    monkeypatch.setenv("THEO_ENABLE_CONSOLE_TRACES", "1")
    monkeypatch.setattr(app_factory, "get_settings", fail_get_settings)
    monkeypatch.setattr(app_factory, "allow_insecure_startup", lambda: False)
    monkeypatch.setattr(app_factory, "get_settings_secret", lambda: "secret")

    monkeypatch.setattr(
        app_factory, "configure_console_tracer", lambda: calls.setdefault("console_tracer", True)
    )

    def record_configure_cors(app: FastAPI, *, allow_origins):
        calls["cors"] = tuple(allow_origins)

    monkeypatch.setattr(app_factory, "configure_cors", record_configure_cors)
    monkeypatch.setattr(app_factory, "install_error_reporting", lambda app: calls.setdefault("error_reporting", True))
    monkeypatch.setattr(app_factory, "register_health_routes", lambda app: calls.setdefault("health_routes", True))
    monkeypatch.setattr(app_factory, "register_trace_handlers", lambda app: calls.setdefault("trace_handlers", True))
    monkeypatch.setattr(app_factory, "install_error_handlers", lambda app: calls.setdefault("error_handlers", True))

    sentinel_dependencies = object()

    def fake_get_security_dependencies():
        calls["security_dependencies"] = True
        return sentinel_dependencies

    monkeypatch.setattr(app_factory, "get_security_dependencies", fake_get_security_dependencies)

    def fake_include_router_registrations(app: FastAPI, *, security_dependencies):
        calls["included_dependencies"] = security_dependencies

    monkeypatch.setattr(app_factory, "include_router_registrations", fake_include_router_registrations)

    class DummyVersionManager:
        def register_version(self, *args, **kwargs):
            calls["version_registered"] = (args, kwargs)

    monkeypatch.setattr(app_factory, "get_version_manager", lambda: DummyVersionManager())
    monkeypatch.setattr(app_factory, "register_metrics_endpoint", lambda app: calls.setdefault("metrics", True))

    app = app_factory.create_app(settings=DummySettings())

    assert isinstance(app, FastAPI)
    assert calls["cors"] == tuple(DummySettings.cors_allowed_origins)
    assert calls["included_dependencies"] is sentinel_dependencies
    assert calls["version_registered"][0] == ("1.0",)
    assert calls["version_registered"][1] == {"is_default": True}
    assert calls["security_dependencies"] is True
    assert calls["metrics"] is True
    assert calls["console_tracer"] is True


def test_create_app_configures_lifespan(monkeypatch):
    monkeypatch.setattr(app_factory, "allow_insecure_startup", lambda: False)
    monkeypatch.setattr(app_factory, "get_settings_secret", lambda: "secret")
    monkeypatch.setattr(app_factory, "get_settings", lambda: SimpleNamespace(
        auth_allow_anonymous=False,
        api_keys=["dummy"],
        cors_allowed_origins=[],
        has_auth_jwt_credentials=lambda: False,
    ))

    monkeypatch.setattr(app_factory, "configure_cors", lambda app, *, allow_origins: None)
    monkeypatch.setattr(app_factory, "install_error_reporting", lambda app: None)
    monkeypatch.setattr(app_factory, "register_health_routes", lambda app: None)
    monkeypatch.setattr(app_factory, "register_trace_handlers", lambda app: None)
    monkeypatch.setattr(app_factory, "install_error_handlers", lambda app: None)
    monkeypatch.setattr(app_factory, "get_security_dependencies", lambda: [])
    monkeypatch.setattr(app_factory, "include_router_registrations", lambda app, *, security_dependencies: None)
    monkeypatch.setattr(app_factory, "get_version_manager", lambda: SimpleNamespace(register_version=lambda *args, **kwargs: None))
    monkeypatch.setattr(app_factory, "register_metrics_endpoint", lambda app: None)
    app = app_factory.create_app()

    assert app.router.lifespan_context is not None
    wrapped = getattr(app.router.lifespan_context, "__wrapped__", None)
    assert wrapped is not None
    assert wrapped.__module__ == bootstrap_lifespan.__module__
    assert wrapped.__qualname__ == bootstrap_lifespan.__qualname__
