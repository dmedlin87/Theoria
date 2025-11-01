"""RAG workflow pipeline regression tests."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, Iterator
from unittest.mock import MagicMock

import pytest

from theo.application.facades import telemetry as telemetry_facade
from theo.infrastructure.api.app.ai.rag import chat as rag_chat
from theo.infrastructure.api.app.ai.rag.guardrails import GuardrailError
from theo.infrastructure.api.app.ai.rag.reasoning import ReasoningOutcome
from theo.infrastructure.api.app.models.search import (
    HybridSearchFilters,
    HybridSearchResult,
)


class _StubTelemetryProvider:
    """Minimal telemetry provider capturing workflow activity."""

    def __init__(self) -> None:
        self.instrumented: list[tuple[str, dict[str, Any]]] = []
        self.events: list[tuple[str, dict[str, Any]]] = []
        self.counters: list[tuple[str, float, dict[str, Any]]] = []

    @contextmanager
    def instrument_workflow(self, workflow: str, **attributes: Any) -> Iterator[Any]:
        span = SimpleNamespace(attributes={})

        def set_attribute(key: str, value: Any) -> None:
            span.attributes[key] = value

        span.set_attribute = set_attribute  # type: ignore[attr-defined]
        self.instrumented.append((workflow, dict(attributes)))
        yield span

    def set_span_attribute(self, span: Any, key: str, value: Any) -> None:
        if span is not None and hasattr(span, "set_attribute"):
            span.set_attribute(key, value)

    def log_workflow_event(self, event: str, *, workflow: str, **context: Any) -> None:
        self.events.append((event, {"workflow": workflow, **context}))

    def record_counter(
        self,
        metric_name: str,
        *,
        amount: float = 1.0,
        labels: dict[str, Any] | None = None,
    ) -> None:
        self.counters.append((metric_name, amount, dict(labels or {})))

    def record_histogram(  # pragma: no cover - not exercised in these tests
        self,
        metric_name: str,
        *,
        value: float,
        labels: dict[str, Any] | None = None,
    ) -> None:
        self.counters.append((metric_name, value, dict(labels or {})))


def _result_from_citation(citation: Any, *, rank: int = 1) -> HybridSearchResult:
    return HybridSearchResult.model_validate(
        {
            "id": citation.passage_id,
            "document_id": citation.document_id,
            "text": citation.snippet,
            "osis_ref": citation.osis,
            "snippet": citation.snippet,
            "rank": rank,
            "score": 0.8 + rank,
        }
    )


@pytest.fixture
def telemetry_provider(monkeypatch: pytest.MonkeyPatch) -> _StubTelemetryProvider:
    provider = _StubTelemetryProvider()
    monkeypatch.setattr(telemetry_facade, "_provider", provider)
    return provider


def test_guarded_pipeline_compose_builds_prompt_and_records_metrics(
    monkeypatch: pytest.MonkeyPatch, regression_factory, telemetry_provider: _StubTelemetryProvider
) -> None:
    citations = regression_factory.rag_citations(2)
    results = [_result_from_citation(citation, rank=i + 1) for i, citation in enumerate(citations)]
    question = regression_factory.question()
    filters = HybridSearchFilters(topic_domain="theology")
    memory_context = regression_factory.conversation_highlights()

    prompt_context_payloads: list[dict[str, Any]] = []
    prompt_calls: list[str | None] = []
    summary_calls: list[list[HybridSearchResult]] = []

    class DummyPromptContext:
        def __init__(self, **payload: Any) -> None:
            prompt_context_payloads.append(payload)

        def build_summary(self, ordered_results: list[HybridSearchResult]) -> tuple[str, list[str]]:
            summary_calls.append(ordered_results)
            text = "Summary from context"
            return text, [text]

        def build_prompt(self, prompt_question: str | None) -> str:
            prompt_calls.append(prompt_question)
            return f"prompt::{prompt_question}"

    monkeypatch.setattr(rag_chat, "PromptContext", DummyPromptContext)
    monkeypatch.setattr(rag_chat, "apply_guardrail_profile", lambda results, filters=None: (list(results), {"profile": "default"}))
    monkeypatch.setattr(rag_chat, "build_citations", lambda results: list(citations))
    monkeypatch.setattr(rag_chat, "build_retrieval_digest", lambda ordered: "digest-hash")
    monkeypatch.setattr(rag_chat, "build_cache_key", lambda **_: "cache-key")
    monkeypatch.setattr(rag_chat, "extract_cache_key_suffix", lambda key: "key-suffix")
    monkeypatch.setattr(rag_chat, "load_cached_answer", lambda cache_key, cache=None: None)

    validation_events: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        rag_chat,
        "validate_model_completion",
        lambda completion, citations: {
            "status": "passed",
            "citation_count": len(citations),
            "cited_indices": [citation.index for citation in citations],
        },
    )
    monkeypatch.setattr(rag_chat, "ensure_completion_safe", lambda completion: None)
    monkeypatch.setattr(
        rag_chat,
        "record_validation_event",
        lambda status, **ctx: validation_events.append((status, ctx)),
    )

    stored_payloads: list[dict[str, Any]] = []
    monkeypatch.setattr(
        rag_chat,
        "store_cached_answer",
        lambda cache_key, *, answer, validation, cache=None: stored_payloads.append(
            {"key": cache_key, "answer": answer, "validation": validation}
        ),
    )

    generation_records: list[tuple[float | None, str | None]] = []
    monkeypatch.setattr(
        rag_chat,
        "record_generation_result",
        lambda span, *, latency_ms, completion: generation_records.append((latency_ms, completion)),
    )

    final_cache_statuses: list[str] = []
    monkeypatch.setattr(rag_chat, "set_final_cache_status", lambda span, status: final_cache_statuses.append(status))

    class DummySpan:
        def __init__(self) -> None:
            self.attributes: dict[str, Any] = {}

        def set_attribute(self, key: str, value: Any) -> None:
            self.attributes[key] = value

        def record_exception(self, exc: Exception) -> None:  # pragma: no cover - defensive
            self.attributes.setdefault("exceptions", []).append(exc)

    @contextmanager
    def dummy_generation_span(*_args: Any, **_kwargs: Any) -> Iterator[DummySpan]:
        yield DummySpan()

    monkeypatch.setattr(rag_chat, "generation_span", dummy_generation_span)

    def _reasoning_review(**kwargs: Any) -> ReasoningOutcome:
        return ReasoningOutcome(
            answer=kwargs["answer"] + "\n[critique applied]",
            original_answer=kwargs["answer"],
            critique=None,
            revision=None,
            reasoning_trace="trace",
        )

    monkeypatch.setattr(rag_chat, "run_reasoning_review", _reasoning_review)

    router_calls: list[tuple[str, str, str, str | None]] = []

    class DummyRouter:
        def iter_candidates(self, workflow: str, model_hint: str | None = None):
            assert workflow == "rag"
            yield SimpleNamespace(name="primary", model="gpt-primary")

        def execute_generation(
            self,
            *,
            workflow: str,
            model: Any,
            prompt: str,
            reasoning_mode: str | None = None,
            **_kwargs: Any,
        ) -> Any:
            router_calls.append((workflow, model.name, prompt, reasoning_mode))
            return SimpleNamespace(output="Generated answer body", latency_ms=25, cost=0.2)

    router = DummyRouter()
    monkeypatch.setattr(rag_chat, "get_router", lambda session, registry=None: router)

    pipeline = rag_chat.GuardedAnswerPipeline(session=MagicMock(), registry=SimpleNamespace())
    answer = pipeline.compose(
        question=question,
        results=results,
        filters=filters,
        memory_context=memory_context,
        mode="reasoned",
    )

    assert prompt_calls == [question]
    assert summary_calls == [results]
    assert router_calls[0][2] == f"prompt::{question}"
    assert answer.summary == "Summary from context"
    assert answer.guardrail_profile == {"profile": "default"}
    assert "Sources:" in answer.model_output
    assert answer.model_name == "primary"
    assert final_cache_statuses[-1] in {"refresh", "hit"}
    assert stored_payloads and stored_payloads[0]["validation"]["status"] == "passed"
    assert validation_events[0][0] == "passed"
    assert prompt_context_payloads and prompt_context_payloads[0]["citations"] == citations
    assert prompt_context_payloads[0]["memory_context"] == memory_context
    assert prompt_context_payloads[0]["filters"] == filters
    assert generation_records and generation_records[0][0] == 25
    cache_events = [event for event in telemetry_provider.events if event[0] == "workflow.guardrails_cache"]
    assert cache_events, "expected guardrails cache telemetry to be recorded"
    assert telemetry_provider.counters, "expected cache metric to be incremented"


def test_guarded_pipeline_uses_cached_answer_for_performance(
    monkeypatch: pytest.MonkeyPatch, regression_factory, telemetry_provider: _StubTelemetryProvider
) -> None:
    citations = regression_factory.rag_citations(1)
    cached_answer = regression_factory.rag_answer(citations=citations, model_name="cached-model")
    results = [_result_from_citation(citations[0])]
    question = regression_factory.question()

    monkeypatch.setattr(rag_chat, "PromptContext", lambda **_: SimpleNamespace(build_summary=lambda results: ("cached", ["cached"]), build_prompt=lambda question: "prompt::cached"))
    monkeypatch.setattr(rag_chat, "apply_guardrail_profile", lambda results, filters=None: (list(results), None))
    monkeypatch.setattr(rag_chat, "build_citations", lambda results: list(citations))
    monkeypatch.setattr(rag_chat, "build_retrieval_digest", lambda ordered: "digest-hash")
    monkeypatch.setattr(rag_chat, "build_cache_key", lambda **_: "cache-key")
    monkeypatch.setattr(rag_chat, "extract_cache_key_suffix", lambda key: "key-suffix")
    monkeypatch.setattr(
        rag_chat,
        "load_cached_answer",
        lambda cache_key, cache=None: {
            "answer": cached_answer.model_dump(mode="json"),
            "model_name": cached_answer.model_name,
        },
    )

    validation_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        rag_chat,
        "validate_model_completion",
        lambda completion, citations: validation_calls.append({"completion": completion, "citations": citations}) or {
            "status": "passed",
            "citation_count": len(citations),
            "cited_indices": [citation.index for citation in citations],
        },
    )
    monkeypatch.setattr(rag_chat, "ensure_completion_safe", lambda completion: None)

    monkeypatch.setattr(rag_chat, "store_cached_answer", lambda *args, **kwargs: pytest.fail("cache store should not be called on hit"))

    class FailingRouter:
        def iter_candidates(self, workflow: str, model_hint: str | None = None):
            yield SimpleNamespace(name="primary", model="gpt-primary")

        def execute_generation(self, **_: Any) -> None:  # pragma: no cover - should not run
            raise AssertionError("router should not execute when cache hits")

    monkeypatch.setattr(rag_chat, "get_router", lambda session, registry=None: FailingRouter())

    pipeline = rag_chat.GuardedAnswerPipeline(session=MagicMock(), registry=SimpleNamespace())
    answer = pipeline.compose(question=question, results=results, filters=HybridSearchFilters())

    assert answer.model_output == cached_answer.model_output
    assert answer.model_name == "cached-model"
    assert validation_calls and validation_calls[0]["citations"] == citations
    cache_events = [event for event in telemetry_provider.events if event[0] == "workflow.guardrails_cache" and event[1]["status"] == "hit"]
    assert cache_events, "expected cache hit telemetry"


def test_guarded_pipeline_raises_guardrail_error_without_citations(
    monkeypatch: pytest.MonkeyPatch, regression_factory
) -> None:
    citations = regression_factory.rag_citations(1)
    results = [_result_from_citation(citations[0])]
    question = regression_factory.question()

    monkeypatch.setattr(rag_chat, "PromptContext", lambda **_: SimpleNamespace(build_summary=lambda results: ("summary", ["summary"]), build_prompt=lambda question: "prompt"))
    monkeypatch.setattr(rag_chat, "apply_guardrail_profile", lambda results, filters=None: (list(results), None))
    monkeypatch.setattr(rag_chat, "build_citations", lambda results: [])

    pipeline = rag_chat.GuardedAnswerPipeline(session=MagicMock(), registry=SimpleNamespace())

    with pytest.raises(GuardrailError) as excinfo:
        pipeline.compose(question=question, results=results, filters=HybridSearchFilters())

    assert excinfo.value.metadata.get("code") == "retrieval_missing_osis"


def test_guarded_pipeline_raises_generation_error_when_all_models_fail(
    monkeypatch: pytest.MonkeyPatch, regression_factory
) -> None:
    citations = regression_factory.rag_citations(1)
    results = [_result_from_citation(citations[0])]
    question = regression_factory.question()

    monkeypatch.setattr(rag_chat, "PromptContext", lambda **_: SimpleNamespace(build_summary=lambda results: ("summary", ["summary"]), build_prompt=lambda question: "prompt"))
    monkeypatch.setattr(rag_chat, "apply_guardrail_profile", lambda results, filters=None: (list(results), None))
    monkeypatch.setattr(rag_chat, "build_citations", lambda results: list(citations))
    monkeypatch.setattr(rag_chat, "build_retrieval_digest", lambda ordered: "digest-hash")
    monkeypatch.setattr(rag_chat, "build_cache_key", lambda **_: "cache-key")
    monkeypatch.setattr(rag_chat, "extract_cache_key_suffix", lambda key: "suffix")
    monkeypatch.setattr(rag_chat, "load_cached_answer", lambda cache_key, cache=None: None)
    monkeypatch.setattr(rag_chat, "validate_model_completion", lambda completion, citations: {"status": "passed"})
    monkeypatch.setattr(rag_chat, "ensure_completion_safe", lambda completion: None)
    monkeypatch.setattr(rag_chat, "record_generation_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(rag_chat, "record_validation_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(rag_chat, "set_final_cache_status", lambda *args, **kwargs: None)

    class FailingRouter:
        def iter_candidates(self, workflow: str, model_hint: str | None = None):
            yield SimpleNamespace(name="primary", model="gpt-primary")

        def execute_generation(self, **_: Any) -> None:
            raise rag_chat.GenerationError("model failure")

    monkeypatch.setattr(rag_chat, "get_router", lambda session, registry=None: FailingRouter())

    pipeline = rag_chat.GuardedAnswerPipeline(session=MagicMock(), registry=SimpleNamespace())

    with pytest.raises(rag_chat.GenerationError):
        pipeline.compose(question=question, results=results, filters=HybridSearchFilters())


def test_run_guarded_chat_returns_refusal_on_safe_guardrail_error(
    monkeypatch: pytest.MonkeyPatch, regression_factory, telemetry_provider: _StubTelemetryProvider
) -> None:
    results = [_result_from_citation(regression_factory.rag_citation())]
    question = regression_factory.question()
    refusal_answer = regression_factory.rag_answer()

    monkeypatch.setattr(rag_chat, "search_passages", lambda session, query, osis=None, filters=None, k=8: results)
    monkeypatch.setattr(rag_chat, "get_llm_registry", lambda session: SimpleNamespace())

    def _guarded_answer(*_args: Any, **_kwargs: Any) -> None:
        raise GuardrailError("unsafe", safe_refusal=True)

    monkeypatch.setattr(rag_chat, "_guarded_answer", _guarded_answer)
    monkeypatch.setattr(rag_chat, "build_guardrail_refusal", lambda session, reason: refusal_answer)
    feedback_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        rag_chat,
        "record_used_citation_feedback",
        lambda session, **ctx: feedback_calls.append(ctx),
    )

    answer = rag_chat.run_guarded_chat(
        MagicMock(),
        question=question,
        filters=HybridSearchFilters(),
        memory_context=regression_factory.conversation_highlights(),
    )

    assert answer is refusal_answer
    assert feedback_calls, "expected citation feedback to be recorded"
    events = {event for event, _ in telemetry_provider.events}
    assert "workflow.passages_retrieved" in events
    assert "workflow.answer_composed" in events
    assert telemetry_provider.instrumented and telemetry_provider.instrumented[0][0] == "chat"
