from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from theo.application.facades.database import Base, get_engine
from theo.services.api.app.db.seeds import seed_reference_data
from theo.services.api.app.db.run_sql_migrations import run_sql_migrations
from theo.services.api.app.routes import ingest, transcripts


@asynccontextmanager
async def _lifespan(_: FastAPI):
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    run_sql_migrations(engine)
    with Session(engine) as session:
        seed_reference_data(session)
    yield


def _create_app() -> FastAPI:
    app = FastAPI(lifespan=_lifespan)
    app.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
    app.include_router(transcripts.router, prefix="/transcripts", tags=["transcripts"])
    return app


app = _create_app()


SAMPLE_VTT = """WEBVTT

00:00.000 --> 00:04.000
Speaker 1: We read the prologue from John 1:1-3 and ponder its light.

00:04.000 --> 00:08.000
These verses echo the creation of Genesis 1:1-2 and guide our prayers.
"""

SAMPLE_VTT_VARIANT = SAMPLE_VTT + "\n00:08.000 --> 00:12.000\nWe continue reflecting on abiding hope.\n"


def test_transcript_search_filters_by_osis_ranges() -> None:
    with TestClient(app) as client:
        ingest_response = client.post(
            "/ingest/transcript",
            files={"transcript": ("sermon.vtt", SAMPLE_VTT_VARIANT, "text/vtt")},
            data={"frontmatter": json.dumps({"title": "Creation Sermon"})},
        )
        assert ingest_response.status_code == 200, ingest_response.text

        search_response = client.get(
            "/transcripts/search",
            params={"osis": "John.1.1-1.5"},
        )
        assert search_response.status_code == 200, search_response.text

        payload = search_response.json()
        assert payload["total"] > 0
        assert payload[
            "segments"
        ], "Expected at least one segment to match the OSIS range"


def test_transcript_search_accepts_chapter_only_queries() -> None:
    with TestClient(app) as client:
        ingest_response = client.post(
            "/ingest/transcript",
            files={"transcript": ("sermon.vtt", SAMPLE_VTT, "text/vtt")},
            data={"frontmatter": json.dumps({"title": "Creation Sermon"})},
        )
        assert ingest_response.status_code == 200, ingest_response.text

        search_response = client.get("/transcripts/search", params={"osis": "John.1"})
        assert search_response.status_code == 200, search_response.text

        payload = search_response.json()
        assert payload[
            "segments"
        ], "Expected chapter-level OSIS lookup to return results"
        assert any(
            segment["primary_osis"] == "John.1.1" for segment in payload["segments"]
        )
