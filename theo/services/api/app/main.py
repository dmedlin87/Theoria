"""Theo Engine FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .core.database import Base, get_engine
from .routes import documents, ingest, search, verses


@asynccontextmanager
async def lifespan(_: FastAPI):
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    """Create FastAPI application instance."""

    app = FastAPI(title="Theo Engine API", version="0.2.0", lifespan=lifespan)
    app.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
    app.include_router(search.router, prefix="/search", tags=["search"])
    app.include_router(verses.router, prefix="/verses", tags=["verses"])
    app.include_router(documents.router, prefix="/documents", tags=["documents"])

    return app


app = create_app()
