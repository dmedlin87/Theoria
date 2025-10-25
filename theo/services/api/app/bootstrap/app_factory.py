"""FastAPI application factory for the Theo API service."""

from __future__ import annotations

import logging
import os
from fastapi import FastAPI

from theo.application.facades.resilience import set_resilience_policy_factory
from theo.application.facades.research import set_application_resolver
from theo.application.facades.secret_migration import set_llm_registry_saver
from theo.application.facades.runtime import allow_insecure_startup
from theo.application.facades.settings import Settings, get_settings, get_settings_secret
from theo.application.facades.telemetry import set_telemetry_provider

from .. import events as _app_events  # noqa: F401  (ensure handlers register)
from ..services import router_registry as _router_registry  # noqa: F401
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

logger = logging.getLogger(__name__)

__all__ = ["create_app", "ROUTER_REGISTRATIONS", "get_router_registrations"]


def _configure_console_traces(settings: Settings, telemetry_provider: ApiTelemetryProvider) -> None:
    if os.getenv("THEO_ENABLE_CONSOLE_TRACES", "0").lower() in {"1", "true", "yes"}:
        telemetry_provider.configure_console_tracer()


def _enforce_authentication_requirements(settings: Settings) -> None:
    insecure_ok = allow_insecure_startup()
    if settings.auth_allow_anonymous and not insecure_ok:
        message = (
            "THEO_AUTH_ALLOW_ANONYMOUS requires THEO_ALLOW_INSECURE_STARTUP for local"
            " testing. Disable anonymous access or set THEO_ALLOW_INSECURE_STARTUP"
            "=1."
        )
        logger.critical(message)
        raise RuntimeError(message)
    if settings.api_keys or settings.has_auth_jwt_credentials():
        return
    if insecure_ok:
        logger.warning(
            "Starting without API credentials because THEO_ALLOW_INSECURE_STARTUP is"
            " enabled. Do not use this configuration outside isolated development"
            " environments."
        )
        return
    message = (
        "API authentication is not configured. Set THEO_API_KEYS or JWT settings"
        " before starting the service, or enable THEO_ALLOW_INSECURE_STARTUP=1 for"
        " local testing."
    )
    logger.critical(message)
    raise RuntimeError(message)


def _enforce_secret_requirements() -> None:
    if get_settings_secret():
        return
    if allow_insecure_startup():
        logger.warning(
            "Starting without SETTINGS_SECRET_KEY because THEO_ALLOW_INSECURE_STARTUP"
            " is enabled. Secrets will not be persisted securely."
        )
        return
    message = (
        "SETTINGS_SECRET_KEY must be configured before starting the service. Set the"
        " environment variable and restart the service or enable"
        " THEO_ALLOW_INSECURE_STARTUP=1 for local development."
    )
    logger.error(message)
    raise RuntimeError(message)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    resolved_settings = settings or get_settings()

    _enforce_authentication_requirements(resolved_settings)
    _enforce_secret_requirements()

    telemetry_provider = ApiTelemetryProvider()
    set_telemetry_provider(telemetry_provider)
    set_resilience_policy_factory(resilience_policy_factory)
    configure_principal_resolver()
    set_application_resolver(lambda: resolve_application()[0])
    set_llm_registry_saver(save_llm_registry)

    app = FastAPI(title="Theo Engine API", version="0.2.0", lifespan=lifespan)

    app.state.telemetry_provider = telemetry_provider

    _configure_console_traces(resolved_settings, telemetry_provider)
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
