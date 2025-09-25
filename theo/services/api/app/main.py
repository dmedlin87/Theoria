"""Theo Engine FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import Session

from .core.database import Base, get_engine
from .db.seeds import seed_reference_data

from .routes import ai, documents, export, features, ingest, jobs, research, search, verses

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
    app.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
    app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
    app.include_router(search.router, prefix="/search", tags=["search"])
    app.include_router(export.router, prefix="/export", tags=["export"])
    app.include_router(verses.router, prefix="/verses", tags=["verses"])
    app.include_router(documents.router, prefix="/documents", tags=["documents"])
    app.include_router(features.router, prefix="/features", tags=["features"])
    app.include_router(research.router, prefix="/research", tags=["research"])

    app.include_router(ai.router, prefix="/ai", tags=["ai"])

    return app


app = create_app()

