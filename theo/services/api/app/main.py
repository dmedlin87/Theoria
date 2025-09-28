"""Theo Engine FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager

import importlib
import logging
import os
from typing import Callable, Optional, cast

from fastapi import Depends, FastAPI, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from .core.database import Base, get_engine
from .core.settings import get_settings
from .db.seeds import seed_reference_data
from .debug import ErrorReportingMiddleware
from .routes import (
    ai,
    creators,
    documents,
    export,
    features,
    ingest,
    jobs,
    research,
    search,
    trails,
    transcripts,
    verses,
)
from .security import require_principal
from .telemetry import configure_console_tracer
from .tracing import TRACE_ID_HEADER_NAME, get_current_trace_headers
GenerateLatestFn = Callable[[], bytes]
CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"
generate_latest: Optional[GenerateLatestFn] = None

logger = logging.getLogger(__name__)

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
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        seed_reference_data(session)
    yield


def create_app() -> FastAPI:
    """Create FastAPI application instance."""

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
    app.include_router(
        ingest.router, prefix="/ingest", tags=["ingest"], dependencies=security_dependencies
    )
    app.include_router(
        jobs.router, prefix="/jobs", tags=["jobs"], dependencies=security_dependencies
    )
    app.include_router(
        search.router, prefix="/search", tags=["search"], dependencies=security_dependencies
    )
    app.include_router(
        export.router, prefix="/export", tags=["export"], dependencies=security_dependencies
    )
    app.include_router(
        verses.router, prefix="/verses", tags=["verses"], dependencies=security_dependencies
    )
    app.include_router(
        documents.router,
        prefix="/documents",
        tags=["documents"],
        dependencies=security_dependencies,
    )
    app.include_router(
        features.router,
        prefix="/features",
        tags=["features"],
        dependencies=security_dependencies,
    )
    app.include_router(
        research.router,
        prefix="/research",
        tags=["research"],
        dependencies=security_dependencies,
    )
    app.include_router(
        creators.router,
        prefix="/creators",
        tags=["creators"],
        dependencies=security_dependencies,
    )
    app.include_router(
        transcripts.router,
        prefix="/transcripts",
        tags=["transcripts"],
        dependencies=security_dependencies,
    )
    app.include_router(
        trails.router, prefix="/trails", tags=["trails"], dependencies=security_dependencies
    )

    app.include_router(
        ai.router, prefix="/ai", tags=["ai"], dependencies=security_dependencies
    )
    app.include_router(
        ai.settings_router,
        tags=["ai-settings"],
        dependencies=security_dependencies,
    )

    if generate_latest is not None:
        metrics_generator = cast(GenerateLatestFn, generate_latest)

        @app.get("/metrics", tags=["telemetry"])
        def metrics_endpoint() -> PlainTextResponse:
            payload = metrics_generator()
            return PlainTextResponse(payload, media_type=CONTENT_TYPE_LATEST)

    return app


def _enforce_secret_requirements() -> None:
    settings = get_settings()
    if settings.settings_secret_key:
        return
    if not _secret_features_enabled():
        return
    message = (
        "SETTINGS_SECRET_KEY must be configured to use the AI registry and provider "
        "settings APIs. Set the environment variable and restart the service."
    )
    logger.error(message)
    raise RuntimeError(message)


def _secret_features_enabled() -> bool:
    toggle = os.getenv("THEO_DISABLE_AI_SETTINGS", "0").lower()
    return toggle not in {"1", "true", "yes"}


app = create_app()
