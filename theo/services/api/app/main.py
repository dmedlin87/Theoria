"""Theo Engine FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager

import os

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from .core.database import Base, get_engine
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
from .telemetry import configure_console_tracer

try:  # pragma: no cover - optional dependency
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
except ImportError:  # pragma: no cover - graceful degradation
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"
    generate_latest = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        seed_reference_data(session)
    yield


def create_app() -> FastAPI:
    """Create FastAPI application instance."""

    app = FastAPI(title="Theo Engine API", version="0.2.0", lifespan=lifespan)
    if os.getenv("THEO_ENABLE_CONSOLE_TRACES", "0").lower() in {"1", "true", "yes"}:
        configure_console_tracer()
    app.add_middleware(
        ErrorReportingMiddleware,
        extra_context={"service": "api"},
    )
    app.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
    app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
    app.include_router(search.router, prefix="/search", tags=["search"])
    app.include_router(export.router, prefix="/export", tags=["export"])
    app.include_router(verses.router, prefix="/verses", tags=["verses"])
    app.include_router(documents.router, prefix="/documents", tags=["documents"])
    app.include_router(features.router, prefix="/features", tags=["features"])
    app.include_router(research.router, prefix="/research", tags=["research"])
    app.include_router(creators.router, prefix="/creators", tags=["creators"])
    app.include_router(transcripts.router, prefix="/transcripts", tags=["transcripts"])
    app.include_router(trails.router, prefix="/trails", tags=["trails"])

    app.include_router(ai.router, prefix="/ai", tags=["ai"])
    app.include_router(ai.settings_router, tags=["ai-settings"])

    if generate_latest is not None:

        @app.get("/metrics", tags=["telemetry"])
        def metrics_endpoint() -> PlainTextResponse:
            payload = generate_latest()
            return PlainTextResponse(payload, media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
