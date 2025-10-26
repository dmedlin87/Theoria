"""FastAPI application factory for the Theo API service."""

from __future__ import annotations

import logging
from fastapi import FastAPI

from theo.application.facades.resilience import set_resilience_policy_factory
from theo.application.facades.research import set_application_resolver
from theo.application.facades.secret_migration import set_llm_registry_saver
from theo.application.facades.runtime import allow_insecure_startup
from theo.application.facades.settings import Settings, get_settings, get_settings_secret
from theo.application.facades.telemetry import set_telemetry_provider

from .. import events as _app_events  # noqa: F401  (ensure handlers register)
from ..infra import router_registry as _router_registry  # noqa: F401
from ..error_handlers import install_error_handlers
from ..adapters.resilience import resilience_policy_factory
from ..adapters.security import configure_principal_resolver
from ..adapters.telemetry import ApiTelemetryProvider
from ..ai.registry import save_llm_registry
from ..versioning import get_version_manager
from theo.services.bootstrap import resolve_application
from .lifecycle import lifespan
from .middleware import (
    configure_cors,
    get_security_dependencies,
    install_error_reporting,
    register_trace_handlers,
)
from .routes import (
    ROUTER_REGISTRATIONS,
    get_router_registrations,
    include_router_registrations,
    mount_mcp,
    register_health_routes,
    register_metrics_endpoint,
)
from .runtime_checks import (
    configure_console_traces,
    enforce_authentication_requirements,
    enforce_secret_requirements,
    should_enable_console_traces,
)

logger = logging.getLogger(__name__)

__all__ = ["create_app", "ROUTER_REGISTRATIONS", "get_router_registrations"]


def configure_console_tracer() -> None:
    """Compatibility hook used by unit tests to observe console tracing."""

    logger.debug("configure_console_tracer invoked without telemetry provider")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    resolved_settings = settings or get_settings()

    enforce_authentication_requirements(
        resolved_settings,
        allow_insecure_startup=allow_insecure_startup,
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
    configure_principal_resolver()
    set_application_resolver(lambda: resolve_application()[0])
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
    include_router_registrations(app, security_dependencies=security_dependencies)

    # Initialize API versioning (v1.0 as default for backward compatibility)
    version_manager = get_version_manager()
    version_manager.register_version("1.0", is_default=True)
    logger.info("Registered API version 1.0 as default")

    register_metrics_endpoint(app)
    mount_mcp(app, enabled=resolved_settings.mcp_tools_enabled)

    return app
