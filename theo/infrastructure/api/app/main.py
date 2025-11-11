"""Theo Engine FastAPI application entrypoint."""

from __future__ import annotations

import inspect
import logging
import os
from functools import wraps
from typing import Any

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from starlette.responses import Response

from theo.application.facades.runtime import (
    allow_insecure_startup,
    current_runtime_environment,
)
from theo.application.facades.settings import get_settings, get_settings_secret

from .bootstrap import ROUTER_REGISTRATIONS, create_app
from .bootstrap.lifecycle import lifespan
from .bootstrap.middleware import (
    configure_cors as _configure_cors_impl,
    install_error_reporting as _install_error_reporting,
    register_trace_handlers as _register_trace_handlers_impl,
)
from .bootstrap.middleware import _attach_trace_headers as _attach_trace_headers_impl
from .bootstrap.routes import register_health_routes as _register_health_routes_impl
from .bootstrap.routes import CONTENT_TYPE_LATEST as _DEFAULT_CONTENT_TYPE
from .bootstrap.routes import generate_latest as _default_generate_latest
from .bootstrap.runtime_checks import (
    configure_console_traces as _configure_console_traces_impl,
    enforce_authentication_requirements as _enforce_authentication_requirements_impl,
    enforce_secret_requirements as _enforce_secret_requirements_impl,
    should_enable_console_traces,
)

logger = logging.getLogger(__name__)

generate_latest = _default_generate_latest
CONTENT_TYPE_LATEST = _DEFAULT_CONTENT_TYPE

# Compatibility exports used across the test-suite
install_error_reporting = _install_error_reporting
register_trace_handlers = _register_trace_handlers_impl


def configure_console_tracer() -> None:
    """Placeholder console tracer used by unit tests."""

    logger.debug("Console tracer configuration requested")


def _configure_console_traces(settings: Any) -> None:
    """Invoke the shared console trace configurator."""

    _configure_console_traces_impl(
        settings,
        console_tracer=configure_console_tracer,
        should_enable=should_enable_console_traces,
    )


def _configure_cors(app: FastAPI, settings: Any) -> None:
    """Proxy helper that applies CORS configuration to ``app``."""

    allow_origins = getattr(settings, "cors_allowed_origins", None)
    _configure_cors_impl(app, allow_origins=allow_origins)


def _register_health_routes(app: FastAPI) -> None:
    """Expose API health endpoints using the shared bootstrap helper."""

    _register_health_routes_impl(app)


def _attach_trace_headers(
    response: Response,
    trace_headers: dict[str, str] | None = None,
) -> Response:
    """Delegate to the bootstrap helper for attaching trace headers."""

    return _attach_trace_headers_impl(response, trace_headers)


def _register_metrics_endpoint(app: FastAPI) -> None:
    """Register the Prometheus metrics endpoint if the client is available."""

    metrics_generator = generate_latest
    if metrics_generator is None:
        return

    content_type = str(CONTENT_TYPE_LATEST or "text/plain; version=0.0.4")

    @app.get("/metrics", tags=["telemetry"])
    def metrics_endpoint() -> PlainTextResponse:
        payload = metrics_generator()
        return PlainTextResponse(payload, media_type=content_type)
def _enforce_authentication_requirements() -> None:
    """Validate authentication prerequisites using shared runtime checks."""

    settings = get_settings()
    _enforce_authentication_requirements_impl(
        settings,
        allow_insecure_startup=allow_insecure_startup,
        get_environment_label=current_runtime_environment,
        logger=logger,
    )


def _enforce_secret_requirements() -> None:
    """Validate SETTINGS_SECRET_KEY requirements via shared runtime checks."""

    _enforce_secret_requirements_impl(
        get_settings_secret,
        allow_insecure_startup=allow_insecure_startup,
        logger=logger,
    )


def _should_patch_httpx() -> bool:
    disabled = os.getenv("THEO_DISABLE_HTTPX_COMPAT_PATCH", "0").lower()
    if disabled in {"1", "true", "yes"}:
        return False
    return True


def _patch_httpx_testclient_compat() -> None:
    try:
        import httpx  # type: ignore[import]
    except Exception:  # pragma: no cover - optional dependency
        return
    try:
        client_signature = inspect.signature(httpx.Client.__init__)
    except (AttributeError, ValueError):
        return
    if "app" in client_signature.parameters:
        return
    transport_cls = getattr(httpx, "ASGITransport", None)
    if transport_cls is None:
        return
    original_client_init = httpx.Client.__init__
    if getattr(original_client_init, "__theo_patched__", False):
        return

    @wraps(original_client_init)
    def compat_client_init(self, *args, app=None, transport=None, **kwargs):
        if app is not None and transport is None:
            transport = transport_cls(app=app)
        return original_client_init(self, *args, transport=transport, **kwargs)

    compat_client_init.__theo_patched__ = True  # type: ignore[attr-defined]
    httpx.Client.__init__ = compat_client_init  # type: ignore[assignment]

    async_client_cls = getattr(httpx, "AsyncClient", None)
    if async_client_cls is None:
        return
    original_async_init = async_client_cls.__init__
    try:
        async_signature = inspect.signature(original_async_init)
    except (AttributeError, ValueError):
        return
    if "app" in async_signature.parameters:
        return

    @wraps(original_async_init)
    def compat_async_init(self, *args, app=None, transport=None, **kwargs):
        if app is not None and transport is None:
            transport = transport_cls(app=app)
        return original_async_init(self, *args, transport=transport, **kwargs)

    compat_async_init.__theo_patched__ = True  # type: ignore[attr-defined]
    async_client_cls.__init__ = compat_async_init  # type: ignore[assignment]


if _should_patch_httpx():
    _patch_httpx_testclient_compat()

app = create_app()

__all__ = ["app", "create_app", "ROUTER_REGISTRATIONS", "lifespan"]
