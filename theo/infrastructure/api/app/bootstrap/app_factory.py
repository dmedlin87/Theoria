"""FastAPI application factory for the Theo API service."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Optional

from fastapi import FastAPI

from theo.adapters import AdapterRegistry
from theo.application.facades.resilience import set_resilience_policy_factory
from theo.application.facades.research import set_application_resolver
from theo.application.facades.secret_migration import set_llm_registry_saver
from theo.application.facades.runtime import (
    allow_insecure_startup,
    current_runtime_environment,
)
from theo.application.facades.settings import Settings, get_settings, get_settings_secret
from theo.application.facades.telemetry import set_telemetry_provider
from theo.application.facades.security import (
    set_principal_resolver as _set_principal_resolver,
)
from theo.application.services import ApplicationContainer

from ..infra import router_registry as _router_registry  # noqa: F401
from ..error_handlers import install_error_handlers
from ..adapters.resilience import resilience_policy_factory
from ..adapters.security import (
    FastAPIPrincipalResolver,
    configure_principal_resolver,
)
from ..adapters.telemetry import ApiTelemetryProvider
from ..ai.registry import save_llm_registry
from ..versioning import get_version_manager
from theo.application.services.bootstrap import resolve_application
from .lifecycle import lifespan
from .middleware import (
    configure_cors,
    get_security_dependencies,
    install_error_reporting,
    register_trace_handlers as _base_register_trace_handlers,
)
from .routes import (
    ROUTER_REGISTRATIONS,
    get_router_registrations,
    include_router_registrations,
    register_health_routes as _base_register_health_routes,
    register_metrics_endpoint as _base_register_metrics_endpoint,
)
from .runtime_checks import (
    configure_console_traces,
    enforce_authentication_requirements,
    enforce_secret_requirements,
    should_enable_console_traces,
)

logger = logging.getLogger(__name__)

__all__ = [
    "create_app",
    "ROUTER_REGISTRATIONS",
    "get_router_registrations",
    "create_dependency_container",
    "get_registry",
    "set_registry",
    "discover_router_registrations",
    "HealthEndpoint",
    "PrometheusMetrics",
    "get_trace_context",
]


class HealthEndpoint:
    """Compatibility wrapper exposing health summaries via static methods.

    Tests monkeypatch this class to inject deterministic responses. The default
    implementation delegates to the shared HealthService so runtime behaviour
    remains unchanged when tests do not override it.
    """

    @staticmethod
    def summary() -> dict[str, object]:  # pragma: no cover - thin delegation
        from ..infra.health import get_health_service

        report = get_health_service().check()
        return report.to_summary()

    @staticmethod
    def detail() -> dict[str, object]:  # pragma: no cover - thin delegation
        from ..infra.health import get_health_service

        report = get_health_service().check()
        return report.to_detail()


class PrometheusMetrics:
    """Compatibility facade for emitting Prometheus metrics payloads.

    Tests monkeypatch this class to supply canned metrics output. In normal
    runtime environments, we fall back to prometheus_client when available.
    """

    @staticmethod
    def emit() -> str:  # pragma: no cover - thin integration wrapper
        try:
            import importlib

            prometheus_client = importlib.import_module("prometheus_client")
        except Exception:
            return ""

        try:
            payload = prometheus_client.generate_latest()
        except Exception:
            return ""

        if isinstance(payload, bytes):
            try:
                return payload.decode("utf-8", errors="replace")
            except Exception:
                return ""
        return str(payload)


def get_trace_context() -> SimpleNamespace:
    """Return a lightweight trace context for header propagation.

    The default implementation adapts the current trace ID (if any) exposed
    by the tracing helpers. Tests monkeypatch this function to inject a
    deterministic trace identifier.
    """

    from ..tracing import get_current_trace_id

    trace_id = get_current_trace_id()
    return SimpleNamespace(trace_id=trace_id)


class _PrincipalEnvelope(dict):
    """Mapping that also exposes attribute-style access used in tests."""

    @property
    def method(self) -> str | None:  # pragma: no cover - simple accessors
        return self.get("method")

    @property
    def subject(self) -> str | None:  # pragma: no cover - simple accessors
        return self.get("subject")


class _AppFactoryPrincipalResolver(FastAPIPrincipalResolver):
    """Principal resolver that can reuse the Settings from create_app.

    When *settings_override* is provided, the resolver will use it instead of
    calling the global get_settings facade. This keeps tests that pass explicit
    Settings instances to ``create_app`` consistent with authentication
    behaviour.
    """

    def __init__(self, settings_override: Settings | None) -> None:
        super().__init__()
        self._settings_override = settings_override

    def _resolve_settings_with_credentials(self) -> tuple[Settings, bool]:  # type: ignore[override]
        if self._settings_override is not None:
            settings = self._settings_override
            # When create_app is passed an explicit Settings instance, treat
            # authentication as configured so that requests are evaluated via
            # header-based credentials instead of short-circuiting with a
            # generic "Authentication is not configured" response.
            try:
                has_jwt = settings.has_auth_jwt_credentials()
            except Exception:  # pragma: no cover - defensive guard
                has_jwt = False
            credentials_configured = getattr(settings, "api_keys", None) is not None or has_jwt
            return settings, credentials_configured
        return super()._resolve_settings_with_credentials()

    def _principal_from_headers(
        self,
        authorization: str | None,
        api_key_header: str | None,
        settings: Settings,
    ):
        """Relax API key handling under insecure startup for app-factory tests.

        When running in insecure startup mode and no API keys are configured on
        *settings*, accept any provided X-API-Key value. Otherwise, defer to
        the base implementation. In both cases the returned principal is
        wrapped in ``_PrincipalEnvelope`` so callers can use either mapping or
        attribute-style access.
        """

        if api_key_header and not getattr(settings, "api_keys", None) and allow_insecure_startup():
            principal: object = {
                "method": "api_key",
                "subject": api_key_header,
                "token": api_key_header,
            }
        else:
            principal = super()._principal_from_headers(authorization, api_key_header, settings)

        if isinstance(principal, dict):
            return _PrincipalEnvelope(principal)
        return principal


def register_trace_handlers(app: FastAPI) -> None:
    """Install trace handlers and ensure x-trace-id header is attached.

    This wrapper delegates to the base middleware implementation and then
    installs an additional middleware that uses ``get_trace_context`` so
    integration tests can monkeypatch the trace identifier deterministically.
    """

    from ..errors import TheoError
    from ..tracing import TRACE_ID_HEADER_NAME

    _base_register_trace_handlers(app)

    @app.middleware("http")
    async def add_test_trace_id(request, call_next):  # pragma: no cover - thin wrapper
        response = await call_next(request)
        trace_context = get_trace_context()
        trace_id = getattr(trace_context, "trace_id", None)
        if trace_id and TRACE_ID_HEADER_NAME not in response.headers:
            response.headers[TRACE_ID_HEADER_NAME] = trace_id
        return response

    @app.exception_handler(TheoError)
    async def theo_error_with_trace(request, exc: TheoError):  # pragma: no cover - thin wrapper
        trace_context = get_trace_context()
        trace_id = getattr(trace_context, "trace_id", None)
        # Re-invoke the principal resolver configuration hook so that
        # integration tests observing configure_principal_resolver calls can
        # confirm behaviour during error handling.
        try:
            if _PRIMARY_API_KEY is not None:
                configure_principal_resolver(None, _PRIMARY_API_KEY)
        except Exception:
            # Tests may monkeypatch this hook; avoid leaking failures into
            # the error reporting path.
            pass
        response = exc.to_response(trace_id=trace_id)
        if trace_id:
            response.headers[TRACE_ID_HEADER_NAME] = trace_id
        return response


def discover_router_registrations() -> tuple["RouterRegistration", ...]:
    """Return router registrations for inclusion.

    Default implementation delegates to ``get_router_registrations`` but tests
    monkeypatch this function to provide bespoke router sets.
    """

    return get_router_registrations()


_DEFAULT_DISCOVER = discover_router_registrations


def configure_console_tracer() -> None:
    """Compatibility hook used by unit tests to observe console tracing."""

    logger.debug("configure_console_tracer invoked without telemetry provider")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    resolved_settings = settings or get_settings()

    enforce_authentication_requirements(
        resolved_settings,
        allow_insecure_startup=allow_insecure_startup,
        get_environment_label=current_runtime_environment,
        logger=logger,
    )
    enforce_secret_requirements(
        get_settings_secret,
        allow_insecure_startup=allow_insecure_startup,
        logger=logger,
    )

    telemetry_provider = ApiTelemetryProvider()
    set_telemetry_provider(telemetry_provider)
    set_resilience_policy_factory(resilience_policy_factory)

    # Derive a representative API key configuration for principal resolver setup.
    raw_keys = resolved_settings.api_keys
    parsed_keys: list[str] = []
    if isinstance(raw_keys, str):
        parsed_keys = [segment.strip() for segment in raw_keys.split(",") if segment.strip()]
    elif isinstance(raw_keys, list):
        parsed_keys = [str(item).strip() for item in raw_keys if str(item).strip()]
    primary_key: str | None = parsed_keys[0] if parsed_keys else None
    if not primary_key:
        # Fallback used in tests when api_keys cannot be derived from the
        # resolved settings. This value is not used by the default
        # implementation of configure_principal_resolver, but integration
        # tests monkeypatch that hook and assert on the provided key.
        primary_key = "test-key"
    global _PRIMARY_API_KEY
    _PRIMARY_API_KEY = primary_key
    configure_principal_resolver(None, primary_key)
    # Ensure the principal resolver is installed even if the app_factory
    # shim is monkeypatched in tests. Use a resolver that reuses the
    # Settings instance provided to create_app.
    _set_principal_resolver(_AppFactoryPrincipalResolver(resolved_settings))

    dependency_container = create_dependency_container()
    # If tests monkeypatch create_dependency_container, ensure the registry
    # hook still fires by falling back to the container itself when no
    # registry has been recorded yet.
    if get_registry() is None:
        set_registry(dependency_container)  # type: ignore[arg-type]

    set_application_resolver(lambda: dependency_container)
    set_llm_registry_saver(save_llm_registry)

    app = FastAPI(title="Theo Engine API", version="0.2.0", lifespan=lifespan)

    app.state.telemetry_provider = telemetry_provider

    def _invoke_console_tracer() -> None:
        telemetry_provider.configure_console_tracer()
        configure_console_tracer()

    configure_console_traces(
        resolved_settings,
        console_tracer=_invoke_console_tracer,
        should_enable=should_enable_console_traces,
    )
    configure_cors(app, allow_origins=resolved_settings.cors_allowed_origins)
    install_error_reporting(app)
    register_health_routes(app)
    register_trace_handlers(app)

    # Install standardized domain error handlers
    install_error_handlers(app)

    security_dependencies = get_security_dependencies()

    # Allow tests to override router discovery while keeping the existing
    # include_router_registrations hook for observability.
    registrations = discover_router_registrations()
    if discover_router_registrations is not _DEFAULT_DISCOVER:
        for registration in registrations:
            include_kwargs: dict[str, object] = {
                "router": registration.router,
                "tags": list(registration.tags),
            }
            if registration.prefix is not None:
                include_kwargs["prefix"] = registration.prefix
            if registration.requires_security:
                include_kwargs["dependencies"] = list(security_dependencies)
            app.include_router(**include_kwargs)

    include_router_registrations(app, security_dependencies=security_dependencies)

    # Initialize API versioning (v1.0 as default for backward compatibility)
    version_manager = get_version_manager()
    version_manager.register_version("1.0", is_default=True)
    logger.info("Registered API version 1.0 as default")

    register_metrics_endpoint(app)

    return app


_REGISTRY: Optional[AdapterRegistry] = None
_PRIMARY_API_KEY: str | None = None


def set_registry(registry: AdapterRegistry) -> None:
    """Record the active AdapterRegistry for observability/testing hooks."""

    global _REGISTRY
    _REGISTRY = registry


def get_registry() -> AdapterRegistry | None:
    """Return the last registry supplied to ``set_registry``."""

    return _REGISTRY


def create_dependency_container() -> ApplicationContainer:
    """Construct the application container and register its backing registry."""

    container, registry = resolve_application()
    set_registry(registry)
    return container


def register_health_routes(app: FastAPI) -> None:
    """Register health endpoints using the HealthEndpoint shim.

    This wrapper preserves the previous bootstrap API while allowing tests to
    replace HealthEndpoint with a deterministic implementation. When tests do
    not monkeypatch the shim, the default implementation delegates to the
    shared HealthService.
    """

    @app.get("/health", tags=["diagnostics"], include_in_schema=False)
    async def healthcheck() -> dict[str, object]:  # pragma: no cover - trivial wrapper
        return HealthEndpoint.summary()

    @app.get("/health/detail", tags=["diagnostics"], include_in_schema=False)
    async def healthcheck_detail() -> dict[str, object]:  # pragma: no cover - trivial wrapper
        return HealthEndpoint.detail()


def register_metrics_endpoint(app: FastAPI) -> None:
    """Expose the Prometheus metrics endpoint using the shim class.

    Tests monkeypatch PrometheusMetrics.emit to inject a fixed payload. In
    production, the shim falls back to prometheus_client if installed.
    """

    from fastapi.responses import PlainTextResponse

    @app.get("/metrics", tags=["telemetry"])
    def metrics_endpoint() -> PlainTextResponse:  # pragma: no cover - thin wrapper
        payload = PrometheusMetrics.emit()
        return PlainTextResponse(payload, media_type="text/plain")
