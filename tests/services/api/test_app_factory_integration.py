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
    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.app_factory.configure_principal_resolver",
        lambda: principal_configured.append(True),
    )

    application_resolvers: list[object] = []
    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.app_factory.set_application_resolver",
        lambda resolver: application_resolvers.append(resolver),
    )

    registry_savers: list[object] = []
    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.app_factory.set_llm_registry_saver",
        lambda saver: registry_savers.append(saver),
    )

    stub_container = object()
    stub_registry = {"settings": object(), "engine": object()}
    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.app_factory.resolve_application",
        lambda: (stub_container, stub_registry),
    )

    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.app_factory.get_settings_secret",
        lambda: "shared-secret",
    )

    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.routes.generate_latest", lambda: b"metrics"
    )
    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.routes.CONTENT_TYPE_LATEST",
        "text/plain",
    )

    principal_calls: list[tuple[str | None, str | None]] = []

    async def fake_require_principal(
        request: Request,
        authorization: str | None = Header(default=None),
        api_key_header: str | None = Header(default=None, alias="X-API-Key"),
    ) -> dict[str, object]:
        principal_calls.append((authorization, api_key_header))
        if not api_key_header:
            raise HTTPException(status_code=403, detail="Missing API key")
        principal = {"method": "api_key", "subject": api_key_header}
        request.state.principal = principal
        return principal

    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.middleware.require_principal",
        fake_require_principal,
    )

    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.middleware.get_current_trace_headers",
        lambda: {"x-trace-id": "trace-123"},
    )

    # Provide a deterministic router registry for the test application.
    router = APIRouter()

    @router.get("/ping")
    async def ping(request: Request) -> dict[str, object]:
        return {
            "ok": True,
            "principal": getattr(request.state, "principal", None),
        }

    @router.get("/boom")
    async def boom() -> dict[str, object]:
        raise TheoError(
            message="Exploded",
            code="EXPLODED",
            status_code=418,
            hint="Try again",
        )

    registration = RouterRegistration(
        router=router,
        prefix="/demo",
        tags=("demo",),
        requires_security=True,
    )

    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.routes.iter_router_registrations",
        lambda: (registration,),
    )

    summary_payload = {
        "status": "healthy",
        "message": "All systems operational.",
        "checked_at": "2024-01-01T00:00:00+00:00",
        "adapters": {"dummy": "healthy"},
    }
    detail_payload = {
        "status": "healthy",
        "message": "All systems operational.",
        "checked_at": "2024-01-01T00:00:00+00:00",
        "adapters": [
            {
                "name": "dummy",
                "status": "healthy",
                "latency_ms": 1.23,
                "message": "ok",
            }
        ],
    }

    class DummyReport(SimpleNamespace):
        def to_summary(self) -> dict[str, object]:
            return summary_payload

        def to_detail(self) -> dict[str, object]:
            return detail_payload

    monkeypatch.setattr(
        "theo.services.api.app.infra.health.get_health_service",
        lambda: SimpleNamespace(check=lambda: DummyReport()),
    )

    class EnvState(SimpleNamespace):
        pass

    state = EnvState(
        telemetry_instances=telemetry_instances,
        registered_providers=registered_providers,
        resilience_factories=resilience_factories,
        principal_configured=principal_configured,
        application_resolvers=application_resolvers,
        registry_savers=registry_savers,
        principal_calls=principal_calls,
        stub_container=stub_container,
        stub_registry=stub_registry,
        health_summary=summary_payload,
        health_detail=detail_payload,
    )
    return state


def _build_settings() -> Settings:
    return Settings(
        api_keys=["test-key"],
        settings_secret_key="shared-secret",
        cors_allowed_origins=["https://example.test"],
        mcp_tools_enabled=False,
    )


def test_create_app_installs_routes_and_middlewares(
    patched_app_environment: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.app_factory.allow_insecure_startup",
        lambda: True,
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
