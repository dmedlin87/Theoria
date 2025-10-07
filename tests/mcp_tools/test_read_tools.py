from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from jsonschema import validate

from mcp_server import schemas
from mcp_server.tools import read
from theo.services.api.app.models.search import HybridSearchResult
from theo.services.api.app.models.verses import (
    VerseTimelineBucket,
    VerseTimelineResponse,
)


@contextmanager
def _fake_session_scope():
    yield SimpleNamespace()


@pytest.fixture(autouse=True)
def patch_session_scope(monkeypatch):
    monkeypatch.setattr(read, "_session_scope", _fake_session_scope)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio("asyncio")
async def test_search_library_schema_valid(monkeypatch):
    result = HybridSearchResult(
        id="passage-1",
        document_id="doc-1",
        text="In the beginning was the Word",
        osis_ref="John.1.1",
        snippet="In the beginning was the Word",
        rank=1,
        document_title="Gospel of John",
        highlights=["Word"],
    )
    monkeypatch.setattr(read, "hybrid_search", lambda session, req: [result])

    request = schemas.SearchLibraryRequest(
        request_id="req-1",
        query="Word",
        limit=5,
    )

    response = await read.search_library(request, end_user_id="user-7")
    payload = response.model_dump()
    validate(payload, schemas.SearchLibraryResponse.model_json_schema())
    assert payload["results"][0]["snippet_html"].count("<mark>") == 1


@pytest.mark.anyio("asyncio")
async def test_aggregate_verses_harmonize_schema(monkeypatch):
    verses = [
        SimpleNamespace(osis="John.1.1", text="In the beginning was the Word."),
        SimpleNamespace(osis="John.1.2", text="He was with God."),
        SimpleNamespace(osis="John.1.3", text="In the beginning was the Word."),
    ]
    monkeypatch.setattr(read, "fetch_passage", lambda osis, translation=None: verses)

    request = schemas.AggregateVersesRequest(
        request_id="agg-1",
        osis="John.1.1-3",
        strategy="harmonize",
    )

    response = await read.aggregate_verses(request, end_user_id="user-33")
    payload = response.model_dump()
    validate(payload, schemas.AggregateVersesResponse.model_json_schema())
    assert payload["combined_text"].count("Word") == 1
    assert payload["citations"] == ["John.1.1", "John.1.2", "John.1.3"]


@pytest.mark.anyio("asyncio")
async def test_get_timeline_schema(monkeypatch):
    timeline = VerseTimelineResponse(
        osis="John.1.1",
        window="month",
        buckets=[
            VerseTimelineBucket(
                label="2023-01",
                start=datetime(2023, 1, 1, tzinfo=timezone.utc),
                end=datetime(2023, 2, 1, tzinfo=timezone.utc),
                count=2,
                document_ids=["doc-1"],
                sample_passage_ids=["passage-1"],
            )
        ],
        total_mentions=2,
    )
    monkeypatch.setattr(read, "get_verse_timeline", lambda *args, **kwargs: timeline)

    request = schemas.GetTimelineRequest(
        request_id="time-1",
        osis="John.1.1",
        window="month",
    )

    response = await read.get_timeline(request, end_user_id="user-44")
    payload = response.model_dump()
    validate(payload, schemas.GetTimelineResponse.model_json_schema())
    assert payload["timeline_html"].startswith("<ul")


@pytest.mark.anyio("asyncio")
async def test_quote_lookup_schema(monkeypatch):
    result = HybridSearchResult(
        id="quote-1",
        document_id="doc-quote",
        text="For God so loved the world",
        osis_ref="John.3.16",
        snippet="For God so loved the world",
        rank=1,
        start_char=0,
        end_char=10,
        score=0.92,
    )
    monkeypatch.setattr(read, "hybrid_search", lambda session, req: [result])

    request = schemas.QuoteLookupRequest(
        request_id="quote-req",
        osis="John.3.16",
        limit=1,
    )

    response = await read.quote_lookup(request, end_user_id="user-55")
    payload = response.model_dump()
    validate(payload, schemas.QuoteLookupResponse.model_json_schema())
    assert payload["quotes"][0]["span_end"] == 10
    assert payload["quotes"][0]["snippet_html"].startswith("<p>")
