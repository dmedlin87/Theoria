import sys
from types import ModuleType, SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from starlette.responses import Response

from theo.infrastructure.api.app import main as main_module


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


def test_should_patch_httpx_respects_disable_env(monkeypatch):
    monkeypatch.setenv("THEO_DISABLE_HTTPX_COMPAT_PATCH", "1")
    assert not main_module._should_patch_httpx()

    monkeypatch.setenv("THEO_DISABLE_HTTPX_COMPAT_PATCH", "true")
    assert not main_module._should_patch_httpx()

    monkeypatch.setenv("THEO_DISABLE_HTTPX_COMPAT_PATCH", "no")
    assert main_module._should_patch_httpx()


def test_configure_console_traces_enabled(monkeypatch):
    calls: list[object] = []
    monkeypatch.setenv("THEO_ENABLE_CONSOLE_TRACES", "true")
    monkeypatch.setattr(main_module, "configure_console_tracer", lambda: calls.append(tuple()))

    settings = SimpleNamespace()
    main_module._configure_console_traces(settings)

    assert calls, "console tracer should be configured when env flag is enabled"


def test_configure_console_traces_disabled(monkeypatch):
    calls: list[object] = []
    monkeypatch.delenv("THEO_ENABLE_CONSOLE_TRACES", raising=False)
    monkeypatch.setattr(main_module, "configure_console_tracer", lambda: calls.append(tuple()))

    settings = SimpleNamespace()
    main_module._configure_console_traces(settings)

    assert not calls, "console tracer should not run without env flag"


def test_register_metrics_endpoint_exposes_prometheus_payload(monkeypatch):
    monkeypatch.setattr(main_module, "generate_latest", lambda: b"metric 123")
    monkeypatch.setattr(main_module, "CONTENT_TYPE_LATEST", "text/plain; version=test")

    app = FastAPI()
    main_module._register_metrics_endpoint(app)

    with TestClient(app) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert response.text == "metric 123"
    assert response.headers["content-type"].startswith("text/plain; version=test")


def test_register_metrics_endpoint_skips_when_not_available(monkeypatch):
    monkeypatch.setattr(main_module, "generate_latest", None)

    app = FastAPI()
    main_module._register_metrics_endpoint(app)

    with TestClient(app) as client:
        response = client.get("/metrics")

    assert response.status_code == 404


def test_mount_mcp_registers_route_when_enabled(monkeypatch):
    package = ModuleType("mcp_server")
    server_module = ModuleType("mcp_server.server")
    server_module.app = FastAPI()
    monkeypatch.setitem(sys.modules, "mcp_server", package)
    monkeypatch.setitem(sys.modules, "mcp_server.server", server_module)

    settings = SimpleNamespace(mcp_tools_enabled=True)
    app = FastAPI()

    main_module._mount_mcp(app, settings)

    assert any(getattr(route, "path", None) == "/mcp" for route in app.routes)


def test_mount_mcp_skips_when_disabled(monkeypatch):
    monkeypatch.delenv("THEO_ENABLE_CONSOLE_TRACES", raising=False)
    settings = SimpleNamespace(mcp_tools_enabled=False)
    app = FastAPI()

    main_module._mount_mcp(app, settings)

    assert all(getattr(route, "path", None) != "/mcp" for route in app.routes)


def test_register_health_routes_return_service_data(monkeypatch):
    class FakeReport:
        def to_summary(self):
            return {"status": "ok"}

        def to_detail(self):
            return {"status": "detailed"}

    class FakeService:
        def check(self):
            return FakeReport()

    monkeypatch.setattr(
        "theo.infrastructure.api.app.infra.health.get_health_service",
        lambda: FakeService(),
    )

    app = FastAPI()
    main_module._register_health_routes(app)

    with TestClient(app) as client:
        summary = client.get("/health")
        detail = client.get("/health/detail")

    assert summary.json() == {"status": "ok"}
    assert detail.json() == {"status": "detailed"}
