from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.testclient import TestClient

from theo.application.facades.settings import Settings
from theo.services.api.app.bootstrap.app_factory import create_app
from theo.services.api.app.errors import TheoError
from theo.services.api.app.infra.registry import RouterRegistration


@pytest.fixture()
def patched_app_environment(monkeypatch: pytest.MonkeyPatch):
    telemetry_instances: list[SimpleNamespace] = []

    class DummyTelemetry(SimpleNamespace):
        def __init__(self):
            super().__init__(configured=False)

        def configure_console_tracer(self) -> None:
            self.configured = True

    def fake_telemetry_provider() -> DummyTelemetry:
        provider = DummyTelemetry()
        telemetry_instances.append(provider)
        return provider

    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.app_factory.ApiTelemetryProvider",
        fake_telemetry_provider,
    )

    registered_providers: list[SimpleNamespace] = []
    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.app_factory.set_telemetry_provider",
        registered_providers.append,
    )

    resilience_factories: list[object] = []
    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.app_factory.set_resilience_policy_factory",
        lambda factory: resilience_factories.append(factory),
    )

    principal_configured: list[bool] = []
    principal_calls: list[tuple[str | None, str]] = []

    class StubContainer:
        pass

    stub_container = StubContainer()

    def fake_principal(config: str | None, key: str):
        principal_calls.append((config, key))
        principal_configured.append(True)

    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.app_factory.configure_principal_resolver",
        fake_principal,
    )

    application_resolvers: list = []

    def save_application_resolver(resolver):
        application_resolvers.append(resolver)

    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.app_factory.set_application_resolver",
        save_application_resolver,
    )

    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.app_factory.create_dependency_container",
        lambda: stub_container,
    )

    registry_savers: list = []

    def save_registry(reg):
        registry_savers.append(reg)

    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.app_factory.set_registry",
        save_registry,
    )

    health_summary = {"status": "healthy"}
    health_detail = {"details": []}

    class HealthEndpoint:
        @staticmethod
        def summary():
            return health_summary

        @staticmethod
        def detail():
            return health_detail

    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.app_factory.HealthEndpoint",
        HealthEndpoint,
    )

    trace_context = SimpleNamespace(trace_id="trace-123")

    def get_trace():
        return trace_context

    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.app_factory.get_trace_context",
        get_trace,
    )

    class DummyMetrics:
        @staticmethod
        def emit():
            return "metrics"

    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.app_factory.PrometheusMetrics",
        DummyMetrics,
    )

    env = SimpleNamespace(
        telemetry_instances=telemetry_instances,
        registered_providers=registered_providers,
        resilience_factories=resilience_factories,
        principal_configured=principal_configured,
        principal_calls=principal_calls,
        application_resolvers=application_resolvers,
        stub_container=stub_container,
        registry_savers=registry_savers,
        health_summary=health_summary,
        health_detail=health_detail,
    )

    return env


@pytest.fixture()
def example_router():
    router = APIRouter(prefix="/demo")

    @router.get("/ping")
    async def ping(request: Request):
        principal = request.state.principal
        return {
            "ok": True,
            "principal": {
                "method": principal.method,
                "subject": principal.subject,
            },
        }

    @router.get("/boom")
    async def boom():
        raise TheoError(
            message="Something exploded",
            code="EXPLODED",
            hint="Try again",
            status_code=418,
        )

    return RouterRegistration(router=router, tags=["demo"])


def _build_settings() -> Settings:
    return Settings(
        api_keys=["test-key"],
        settings_secret_key="test-secret",
    )


def test_create_app_with_components(
    patched_app_environment, example_router, monkeypatch: pytest.MonkeyPatch
):
    def fake_discover():
        return [example_router]

    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.app_factory.discover_router_registrations",
        fake_discover,
    )

    settings = _build_settings()
    app = create_app(settings)

    assert patched_app_environment.telemetry_instances
    assert (
        patched_app_environment.registered_providers[0]
        is patched_app_environment.telemetry_instances[0]
    )
    assert patched_app_environment.resilience_factories
    assert patched_app_environment.principal_configured == [True]
    assert patched_app_environment.application_resolvers
    resolver = patched_app_environment.application_resolvers[0]
    assert resolver() is patched_app_environment.stub_container
    assert patched_app_environment.registry_savers

    assert getattr(app.state, "telemetry_provider").configured is False

    client = TestClient(app)

    summary = client.get("/health")
    assert summary.status_code == 200
    assert summary.json() == patched_app_environment.health_summary

    detail = client.get("/health/detail")
    assert detail.status_code == 200
    assert detail.json() == patched_app_environment.health_detail

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert metrics.text == "metrics"
    assert metrics.headers["content-type"].startswith("text/plain")

    response = client.get("/demo/ping", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    body = response.json()
    assert body == {"ok": True, "principal": {"method": "api_key", "subject": "test-key"}}
    assert response.headers["x-trace-id"] == "trace-123"
    assert patched_app_environment.principal_calls == [(None, "test-key")]

    error_response = client.get("/demo/boom", headers={"X-API-Key": "test-key"})
    assert error_response.status_code == 418
    payload = error_response.json()
    assert payload["error"]["code"] == "EXPLODED"
    assert payload["error"]["hint"] == "Try again"
    assert payload["trace_id"] == "trace-123"
    assert error_response.headers["x-trace-id"] == "trace-123"

    assert patched_app_environment.principal_calls == [(None, "test-key"), (None, "test-key")]

    middleware_names = {middleware.cls.__name__ for middleware in app.user_middleware}
    assert "ErrorReportingMiddleware" in middleware_names
    assert any("CORSMiddleware" in name for name in middleware_names)


def test_create_app_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.app_factory.allow_insecure_startup",
        lambda: False,
    )
    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.app_factory.get_settings_secret",
        lambda: "secret",
    )

    settings = Settings(api_keys=[], settings_secret_key="secret")

    with pytest.raises(RuntimeError):
        create_app(settings)


def test_create_app_requires_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.app_factory.allow_insecure_startup",
        lambda: False,
    )

    settings = Settings(api_keys=["key"], settings_secret_key=None)

    with pytest.raises(RuntimeError):
        create_app(settings)
