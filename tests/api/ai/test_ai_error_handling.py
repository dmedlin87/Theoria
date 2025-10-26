"""Tests verifying error handling paths in the guardrailed RAG workflow."""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from theo.services.api.app.ai.rag import workflow
from theo.services.api.app.ai.rag.guardrail_helpers import GuardrailError
from theo.services.api.app.ai.rag.models import RAGAnswer
from theo.services.api.app.models.search import HybridSearchFilters, HybridSearchResult


def _result(*, identifier: str, osis: str | None) -> HybridSearchResult:
    return HybridSearchResult(
        id=identifier,
        document_id=f"doc-{identifier}",
        text="text",
        raw_text=None,
        osis_ref=osis,
        start_char=0,
        end_char=1,
        page_no=None,
        t_start=None,
        t_end=None,
        score=0.5,
        meta=None,
        document_title=f"Document {identifier}",
        snippet="Snippet",
        rank=1,
        highlights=None,
    )


def test_guarded_answer_or_refusal_uses_fallback_results(monkeypatch: pytest.MonkeyPatch) -> None:
    session = object()
    fallback = [_result(identifier="fallback", osis="John.3.16")]

    monkeypatch.setattr(
        workflow,
        "load_passages_for_osis",
        lambda s, osis, **kwargs: fallback,
    )

    captured: dict[str, object] = {}

    def fake_guarded(session_arg, **kwargs):
        captured.update(kwargs)
        return RAGAnswer(summary="s", citations=[])

    monkeypatch.setattr(workflow, "_guarded_answer", fake_guarded)

    answer = workflow._guarded_answer_or_refusal(
        session,
        context="chat",
        question="Q",
        results=[_result(identifier="primary", osis=None)],
        registry="registry",
        model_hint=None,
        recorder=None,
        filters=None,
        memory_context=None,
        osis="John.3.16",
        allow_fallback=True,
    )

    assert answer.summary == "s"
    assert captured["results"] == fallback
    assert captured["allow_fallback"] is True


def test_guarded_answer_or_refusal_returns_refusal_on_safe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = object()
    error = GuardrailError("blocked", safe_refusal=True)

    def fake_guarded(*args, **kwargs):  # pragma: no cover - exercised via raise
        raise error

    sentinel = RAGAnswer(summary="refused", citations=[])

    monkeypatch.setattr(workflow, "_guarded_answer", fake_guarded)
    monkeypatch.setattr(workflow, "build_guardrail_refusal", lambda s, reason=None: sentinel)
    monkeypatch.setattr(workflow, "load_passages_for_osis", lambda *args, **kwargs: [])

    result = workflow._guarded_answer_or_refusal(
        session,
        context="chat",
        question="Q",
        results=[],
        registry="registry",
    )

    assert result is sentinel


def test_guarded_answer_or_refusal_reraises_non_safe_error(monkeypatch: pytest.MonkeyPatch) -> None:
    error = GuardrailError("fail", safe_refusal=False)

    def fake_guarded(*args, **kwargs):
        raise error

    monkeypatch.setattr(workflow, "_guarded_answer", fake_guarded)
    monkeypatch.setattr(workflow, "load_passages_for_osis", lambda *args, **kwargs: [])

    with pytest.raises(GuardrailError) as exc:
        workflow._guarded_answer_or_refusal(
            object(),
            context="chat",
            question="Q",
            results=[],
            registry="registry",
        )

    assert exc.value is error


def test_sermon_prep_guardrail_error_includes_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    @contextmanager
    def _fake_instrument(*args, **kwargs):
        yield None

    monkeypatch.setattr(workflow, "instrument_workflow", _fake_instrument)
    monkeypatch.setattr(workflow, "search_passages", lambda *args, **kwargs: [])
    monkeypatch.setattr(workflow, "log_workflow_event", lambda *args, **kwargs: None)

    filters = HybridSearchFilters(collection="lectionary")

    with pytest.raises(GuardrailError) as exc:
        workflow.generate_sermon_prep_outline(
            object(),
            topic="Advent hope",
            filters=filters,
        )

    error = exc.value
    assert error.safe_refusal is True
    assert error.metadata.get("code") == "sermon_prep_insufficient_context"
    assert error.metadata.get("guardrail") == "retrieval"
    assert error.metadata.get("suggested_action") == "search"
    assert error.metadata.get("filters") == filters.model_dump(exclude_none=True)

