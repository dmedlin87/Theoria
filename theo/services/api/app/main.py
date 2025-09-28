"""Theo Engine FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager

import importlib
import logging
import os
from typing import Callable, Optional, cast

from fastapi import Depends, FastAPI
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

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
    if os.getenv("THEO_ENABLE_CONSOLE_TRACES", "0").lower() in {"1", "true", "yes"}:
        configure_console_tracer()
    app.add_middleware(
        ErrorReportingMiddleware,
        extra_context={"service": "api"},
    )
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
