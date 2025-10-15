"""Theo Engine FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager
import importlib
import inspect
import logging
import os
from functools import wraps
from typing import Callable, Optional, cast

from fastapi import Depends, FastAPI, Request, status
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from theo.application.facades import database as database_module
from theo.application.facades.database import Base, get_engine
from theo.application.facades.runtime import allow_insecure_startup
from theo.application.facades.settings import get_settings
from .db.run_sql_migrations import run_sql_migrations
from .db.seeds import seed_reference_data
from .debug import ErrorReportingMiddleware
from .ingest.exceptions import UnsupportedSourceError
from .errors import TheoError
from .routes import (
    ai,
    analytics,
    creators,
    documents,
    export,
    features,
    ingest,
    jobs,
    notebooks,
    realtime,
    research,
    search,
    trails,
    transcripts,
    verses,
)
from .security import require_principal
from .telemetry import configure_console_tracer
from .tracing import TRACE_ID_HEADER_NAME, get_current_trace_headers
from .services import router_registry as _router_registry  # noqa: F401
from .services.registry import RouterRegistration, iter_router_registrations
GenerateLatestFn = Callable[[], bytes]
CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"
generate_latest: Optional[GenerateLatestFn] = None


logger = logging.getLogger(__name__)


def _patch_httpx_testclient_compat() -> None:
    try:
        import httpx  # type: ignore[import]
    except Exception:
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


_patch_httpx_testclient_compat()

try:  # pragma: no cover - optional dependency
    prometheus_client = importlib.import_module("prometheus_client")
except ImportError:  # pragma: no cover - graceful degradation
    pass
else:
    CONTENT_TYPE_LATEST = cast(str, prometheus_client.CONTENT_TYPE_LATEST)
    generate_latest = cast(GenerateLatestFn, prometheus_client.generate_latest)

@asynccontextmanager
async def lifespan(_: FastAPI):
    engine = get_engine()
    try:
        Base.metadata.create_all(bind=engine)
        run_sql_migrations(engine)
        with Session(engine) as session:
            try:
                seed_reference_data(session)
            except OperationalError as exc:  # pragma: no cover - defensive startup guard
                session.rollback()
                logger.warning(
                    "Skipping reference data seeding due to database error", exc_info=exc
                )
        yield
    finally:
        try:
            engine.dispose()
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.debug("Error disposing database engine during shutdown", exc_info=exc)
        else:
            import gc as _gc
            import time as _time

            _gc.collect()
            _time.sleep(0.01)
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]


def create_app() -> FastAPI:
    """Create FastAPI application instance."""

    _enforce_authentication_requirements()
    _enforce_secret_requirements()
    app = FastAPI(title="Theo Engine API", version="0.2.0", lifespan=lifespan)
    settings = get_settings()
    if os.getenv("THEO_ENABLE_CONSOLE_TRACES", "0").lower() in {"1", "true", "yes"}:
        configure_console_tracer()
    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins,
            allow_credentials=True,
            allow_methods=["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "Accept",
                "Origin",
                "X-Requested-With",
            ],
        )
    app.add_middleware(
        ErrorReportingMiddleware,
        extra_context={"service": "api"},
    )

    @app.get("/health", tags=["diagnostics"], include_in_schema=False)
    async def healthcheck() -> dict[str, str]:
        """Return a simple readiness indicator for infrastructure monitors."""
        return {"status": "ok"}

    def _attach_trace_headers(
        response: Response, trace_headers: dict[str, str] | None = None
    ) -> Response:
        headers = trace_headers or get_current_trace_headers()
        for key, value in headers.items():
            if key not in response.headers:
                response.headers[key] = value
        return response

    @app.middleware("http")
    async def add_trace_headers(request: Request, call_next: RequestResponseEndpoint):
        response = await call_next(request)
        return _attach_trace_headers(response)

    @app.exception_handler(HTTPException)
    async def http_exception_with_trace(request: Request, exc: HTTPException) -> Response:  # type: ignore[override]
        response = await http_exception_handler(request, exc)
        return _attach_trace_headers(response)

    @app.exception_handler(TheoError)
    async def theo_error_handler(request: Request, exc: TheoError) -> Response:
        trace_headers = get_current_trace_headers()
        trace_id = trace_headers.get(TRACE_ID_HEADER_NAME) or request.headers.get(
            TRACE_ID_HEADER_NAME
        )
        if trace_id and TRACE_ID_HEADER_NAME not in trace_headers:
            trace_headers[TRACE_ID_HEADER_NAME] = trace_id
        request.state._last_domain_error = exc  # type: ignore[attr-defined]
        response = exc.to_response(trace_id=trace_id)
        return _attach_trace_headers(response, trace_headers)

    @app.exception_handler(UnsupportedSourceError)
    async def unsupported_source_error_with_trace(
        request: Request, exc: UnsupportedSourceError
    ) -> Response:
        request.state._last_domain_error = exc  # type: ignore[attr-defined]
        response = JSONResponse({"detail": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)
        return _attach_trace_headers(response)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_with_trace(
        request: Request, exc: RequestValidationError
    ) -> Response:  # type: ignore[override]
        response = await request_validation_exception_handler(request, exc)
        return _attach_trace_headers(response)

    @app.exception_handler(Exception)
    async def unhandled_exception_with_trace(request: Request, exc: Exception) -> Response:  # type: ignore[override]
        del exc  # Preserve the signature without exposing details.
        trace_headers = get_current_trace_headers()
        body: dict[str, str] = {"detail": "Internal Server Error"}
        trace_id = trace_headers.get(TRACE_ID_HEADER_NAME)
        if trace_id:
            body["trace_id"] = trace_id
        response = JSONResponse(body, status_code=500)
        return _attach_trace_headers(response, trace_headers)

    security_dependencies = [Depends(require_principal)]
    for registration in iter_router_registrations():
        include_kwargs: dict[str, object] = {
            "router": registration.router,
            "tags": list(registration.tags),
        }
        if registration.prefix is not None:
            include_kwargs["prefix"] = registration.prefix
        if registration.requires_security:
            include_kwargs["dependencies"] = security_dependencies
        app.include_router(**include_kwargs)

    if generate_latest is not None:
        metrics_generator = cast(GenerateLatestFn, generate_latest)

        @app.get("/metrics", tags=["telemetry"])
        def metrics_endpoint() -> PlainTextResponse:
            payload = metrics_generator()
            return PlainTextResponse(payload, media_type=CONTENT_TYPE_LATEST)

    if settings.mcp_tools_enabled:
        try:
            from mcp_server.server import app as mcp_app
        except ImportError as exc:  # pragma: no cover - defensive guard
            logger.warning(
                "MCP tools enabled but server package import failed: %s", exc
            )
        else:
            app.mount("/mcp", mcp_app)
            logger.info("Mounted MCP server at /mcp")

    return app


def _enforce_authentication_requirements() -> None:
    settings = get_settings()
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
    settings = get_settings()
    if settings.settings_secret_key:
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


app = create_app()
ROUTER_REGISTRATIONS: tuple[RouterRegistration, ...] = iter_router_registrations()

