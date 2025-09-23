from fastapi import FastAPI

from .routes import ingest, search, verses, documents


def create_app() -> FastAPI:
    """Create FastAPI application instance."""
    app = FastAPI(title="Theo Engine API", version="0.1.0")

    app.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
    app.include_router(search.router, prefix="/search", tags=["search"])
    app.include_router(verses.router, prefix="/verses", tags=["verses"])
    app.include_router(documents.router, prefix="/documents", tags=["documents"])

    return app


app = create_app()
