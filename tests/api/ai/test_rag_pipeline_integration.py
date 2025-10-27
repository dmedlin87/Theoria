"""Integration-focused tests for the guardrailed RAG chat workflow."""

from __future__ import annotations

from collections import deque

import pytest

from theo.infrastructure.api.app.ai.rag import workflow
from theo.infrastructure.api.app.ai.rag.models import RAGAnswer, RAGCitation
from theo.infrastructure.api.app.models.search import HybridSearchFilters, HybridSearchResult


class _DummySpan:
    """Span stub recording attributes that were set during execution."""

    def __init__(self) -> None:
        self.attributes: deque[tuple[tuple[object, ...], dict[str, object]]] = deque()

    def set_attribute(self, *args: object, **kwargs: object) -> None:  # pragma: no cover - compatibility
        self.attributes.append((args, kwargs))


class _DummySpanContext:
    """Context manager returning a dummy span for instrumentation calls."""

    def __init__(self, span: _DummySpan) -> None:
        self._span = span

    def __enter__(self) -> _DummySpan:  # noqa: D401 - standard context protocol
        return self._span

    def __exit__(self, exc_type, exc, exc_tb) -> None:  # pragma: no cover - no special handling
        return None


def _make_result(*, identifier: str, osis: str | None = None, rank: int = 1) -> HybridSearchResult:
    """Construct a minimal hybrid search result for testing."""

    return HybridSearchResult(
        id=identifier,
        document_id=f"doc-{identifier}",
        text="passage text",
        raw_text=None,
        osis_ref=osis,
        start_char=0,
        end_char=10,
        page_no=None,
        t_start=None,
        t_end=None,
        score=0.42,
        meta=None,
        document_title=f"Document {identifier}",
        snippet=f"Snippet for {identifier}",
        rank=rank,
        highlights=None,
    )


def _make_citation(*, identifier: str, index: int = 1) -> RAGCitation:
    """Construct a minimal citation corresponding to the fabricated result."""

    osis = "John.3.16"
    return RAGCitation(
        index=index,
        osis=osis,
        anchor="John 3:16",
        passage_id=identifier,
        document_id=f"doc-{identifier}",
        document_title=f"Document {identifier}",
        snippet=f"Snippet for {identifier}",
        source_url=None,
    )


def test_run_guarded_chat_records_feedback_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    """``run_guarded_chat`` should propagate retrieval, answer, and feedback payloads."""

    session = object()
    filters = HybridSearchFilters(collection="core")
    results = [_make_result(identifier="1", osis="John.3.16")]

    captured: dict[str, object] = {}
    span = _DummySpan()

    def fake_instrument(workflow_name: str, **kwargs: object) -> _DummySpanContext:
        captured["instrument"] = (workflow_name, kwargs)
        return _DummySpanContext(span)

    monkeypatch.setattr(workflow, "instrument_workflow", fake_instrument)
    monkeypatch.setattr(workflow, "set_span_attribute", lambda *args, **kwargs: None)
    monkeypatch.setattr(workflow, "log_workflow_event", lambda *args, **kwargs: None)

    def fake_search(session_arg, *, query, osis, filters):
        captured["search"] = (session_arg, query, osis, filters)
        return results

    monkeypatch.setattr(workflow, "search_passages", fake_search)
    monkeypatch.setattr(workflow, "get_llm_registry", lambda session_arg: "registry")

    answer = RAGAnswer(summary="summary", citations=[_make_citation(identifier="1")])

    def fake_guarded(session_arg, **kwargs):
        captured["guarded"] = (session_arg, kwargs)
        return answer

    monkeypatch.setattr(workflow, "_guarded_answer_or_refusal", fake_guarded)

    feedback_payloads: list[tuple[object, dict[str, object]]] = []

    def fake_feedback(session_arg, **kwargs):
        feedback_payloads.append((session_arg, kwargs))

    monkeypatch.setattr(workflow, "record_used_citation_feedback", fake_feedback)

    returned = workflow.run_guarded_chat(
        session,
        question="What is hope?",
        filters=filters,
    )

    assert returned is answer
    assert captured["instrument"][0] == "chat"
    assert captured["search"][1:] == ("What is hope?", None, filters)
    # ``_guarded_answer_or_refusal`` receives the same retrieval payload the router would use.
    assert captured["guarded"][1]["results"] == results
    assert feedback_payloads[0][1]["citations"] == answer.citations

