from unittest.mock import MagicMock

import pytest

from theo.infrastructure.api.app.ai.rag import retrieval
from theo.infrastructure.api.app.ai.rag.models import RAGCitation
from theo.infrastructure.api.app.models.search import HybridSearchFilters, HybridSearchResult


def test_passage_retriever_falls_back_to_guardrail(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock()
    retriever = retrieval.PassageRetriever(session)

    primary_result = HybridSearchResult(
        id="primary",
        document_id="doc-1",
        text="",
        snippet="",
        osis_ref=None,
        score=0.1,
        rank=0,
    )
    fallback_result = HybridSearchResult(
        id="fallback",
        document_id="doc-2",
        text="fallback",
        snippet="fallback",
        osis_ref="John.1.1",
        score=0.9,
        rank=1,
    )

    monkeypatch.setattr(
        retrieval,
        "hybrid_search",
        lambda _session, request: [primary_result],
    )
    monkeypatch.setattr(
        retrieval,
        "load_passages_for_osis",
        lambda _session, osis, limit=3: [fallback_result],
    )

    results = retriever.search(
        query="hope",
        osis="John.1.1",
        filters=HybridSearchFilters(),
    )

    assert results == [fallback_result]


def test_record_used_citation_feedback_emits_event(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock()
    calls: list[dict] = []

    def _capture(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(retrieval, "record_feedback_event", _capture)

    result = HybridSearchResult(
        id="passage-1",
        document_id="doc-1",
        text="snippet",
        snippet="snippet",
        osis_ref="Gen.1.1",
        score=1.0,
        rank=1,
    )
    citation = RAGCitation(
        index=1,
        osis="Gen.1.1",
        anchor="v1",
        passage_id="passage-1",
        document_id="doc-1",
        document_title="Genesis",
        snippet="In the beginning",
    )

    retrieval.record_used_citation_feedback(
        session,
        citations=[citation],
        results=[result],
        query="creation",
    )

    assert len(calls) == 1
    payload = calls[0]["kwargs"]
    assert payload["document_id"] == "doc-1"
    assert payload["passage_id"] == "passage-1"
    assert payload["query"] == "creation"
