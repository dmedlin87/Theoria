"""Tests covering retrieval behaviours used by the guardrailed RAG stack."""

from __future__ import annotations

import pytest

from theo.infrastructure.api.app.ai.rag import retrieval
from theo.infrastructure.api.app.ai.rag.models import RAGCitation
from theo.infrastructure.api.app.models.search import HybridSearchFilters, HybridSearchResult


def _result(*, identifier: str, osis: str | None, rank: int = 1) -> HybridSearchResult:
    return HybridSearchResult(
        id=identifier,
        document_id=f"doc-{identifier}",
        text="passage",
        raw_text=None,
        osis_ref=osis,
        start_char=0,
        end_char=5,
        page_no=None,
        t_start=None,
        t_end=None,
        score=0.5,
        meta=None,
        document_title=f"Document {identifier}",
        snippet=f"Snippet {identifier}",
        rank=rank,
        highlights=None,
    )


def _citation(*, identifier: str, index: int = 1) -> RAGCitation:
    return RAGCitation(
        index=index,
        osis="John.3.16",
        anchor="John 3:16",
        passage_id=identifier,
        document_id=f"doc-{identifier}",
        document_title=f"Document {identifier}",
        snippet=f"Snippet {identifier}",
        source_url=None,
    )


def test_passage_retriever_injects_osis_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    session = object()
    retriever = retrieval.PassageRetriever(session)
    filters = HybridSearchFilters()

    def fake_hybrid(session_arg, request):
        assert session_arg is session
        assert request.osis == "John.3.16"
        yield _result(identifier="primary", osis=None)

    fallback = [_result(identifier="fallback", osis="John.3.16")]

    monkeypatch.setattr(retrieval, "hybrid_search", fake_hybrid)
    monkeypatch.setattr(retrieval, "load_passages_for_osis", lambda s, osis: fallback)

    results = retriever.search(query="hope", osis="John.3.16", filters=filters)

    assert results == fallback


def test_record_used_citation_feedback_enriches_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: list[dict[str, object]] = []

    def fake_record(session_arg, **payload):
        recorded.append(payload)

    monkeypatch.setattr(retrieval, "record_feedback_event", fake_record)

    class Recorder:
        trail = type("Trail", (), {"user_id": "user-123"})()

        def record_citations(self, citations):  # pragma: no cover - unused in test
            pass

    citations = [_citation(identifier="1")]
    results = [_result(identifier="1", osis="John.3.16", rank=3)]

    retrieval.record_used_citation_feedback(
        "session",
        citations=citations,
        results=results,
        query="hope",
        recorder=Recorder(),
    )

    assert recorded[0]["user_id"] == "user-123"
    assert recorded[0]["rank"] == 3
    assert recorded[0]["document_id"] == "doc-1"

