"""Tests for the RAG telemetry helpers."""

from __future__ import annotations

import pytest

from theo.services.api.app.ai.rag import telemetry


class DummySpan:
    """Minimal span implementation that records attribute values."""

    def __init__(self) -> None:
        self.attributes: dict[str, object] = {}

    def set_attribute(self, key: str, value: object) -> None:  # pragma: no cover - exercised indirectly
        self.attributes[key] = value


class DummySpanContext:
    """Context manager returned by the fake tracer."""

    def __init__(self) -> None:
        self.span = DummySpan()

    def __enter__(self) -> DummySpan:
        return self.span

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class DummyTracer:
    """Tracer stub that returns a dummy span context."""

    def __init__(self) -> None:
        self.started_spans: list[str] = []

    def start_as_current_span(self, name: str) -> DummySpanContext:
        self.started_spans.append(name)
        return DummySpanContext()


@pytest.fixture()
def patched_tracer(monkeypatch: pytest.MonkeyPatch) -> DummyTracer:
    """Patch the module tracer with a deterministic stub."""

    dummy_tracer = DummyTracer()
    monkeypatch.setattr(telemetry, "_RAG_TRACER", dummy_tracer)
    return dummy_tracer


@pytest.fixture()
def fake_logger(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, object]]]:
    """Capture log_workflow_event calls for assertions."""

    events: list[tuple[str, dict[str, object]]] = []

    def _record(event: str, *, workflow: str, **context: object) -> None:
        events.append((event, {"workflow": workflow, "context": context}))

    monkeypatch.setattr(telemetry, "log_workflow_event", _record)
    return events


def test_generation_span_sets_expected_attributes(patched_tracer: DummyTracer) -> None:
    """generation_span should tag the span with cache and prompt metadata."""

    with telemetry.generation_span(
        "candidate-a",
        "gpt-4",
        cache_status="hit",
        cache_key_suffix="variant-1",
        prompt="Tell me about Romans 8.",
    ) as span:
        assert isinstance(span, DummySpan)

    assert patched_tracer.started_spans == ["rag.execute_generation"]
    assert span.attributes["rag.candidate"] == "candidate-a"
    assert span.attributes["rag.model_label"] == "gpt-4"
    assert span.attributes["rag.cache_status"] == "hit"
    assert span.attributes["rag.cache_key_suffix"] == "variant-1"
    assert span.attributes["rag.prompt_tokens"] > 0


def test_record_generation_result_attaches_latency_and_completion() -> None:
    """record_generation_result should annotate an existing span with metrics."""

    span = DummySpan()

    telemetry.record_generation_result(span, latency_ms=123, completion="final answer")

    assert span.attributes["rag.latency_ms"] == 123
    assert span.attributes["rag.completion_tokens"] > 0


@pytest.mark.parametrize("completion", [None, ""])
def test_record_generation_result_handles_missing_completion(completion: str | None) -> None:
    """Empty completions should not create a completion token attribute."""

    span = DummySpan()

    telemetry.record_generation_result(span, latency_ms=None, completion=completion)

    assert span.attributes == {}


def test_set_final_cache_status_is_noop_for_none_span() -> None:
    """set_final_cache_status should handle None spans gracefully."""

    telemetry.set_final_cache_status(None, cache_status="miss")


def test_record_validation_event_logs_payload(fake_logger: list[tuple[str, dict[str, object]]]) -> None:
    """record_validation_event should log guardrail validation telemetry."""

    telemetry.record_validation_event(
        "passed",
        cache_status="warm",
        cache_key_suffix="demo",
        citation_count=3,
        cited_indices=[0, 2],
    )

    event, payload = fake_logger[-1]
    assert event == "workflow.guardrails_validation"
    assert payload["workflow"] == "rag"
    assert payload["context"]["citation_count"] == 3
    assert payload["context"]["cache_status"] == "warm"


def test_record_answer_event_logs_payload(fake_logger: list[tuple[str, dict[str, object]]]) -> None:
    """record_answer_event should log a chat workflow event."""

    telemetry.record_answer_event(citation_count=5)

    event, payload = fake_logger[-1]
    assert event == "workflow.answer_composed"
    assert payload["workflow"] == "chat"
    assert payload["context"]["citations"] == 5


def test_record_passages_retrieved_logs_payload(fake_logger: list[tuple[str, dict[str, object]]]) -> None:
    """record_passages_retrieved should log retrieval metrics."""

    telemetry.record_passages_retrieved(result_count=7)

    event, payload = fake_logger[-1]
    assert event == "workflow.passages_retrieved"
    assert payload["workflow"] == "chat"
    assert payload["context"]["result_count"] == 7


def test_record_revision_event_logs_payload(fake_logger: list[tuple[str, dict[str, object]]]) -> None:
    """record_revision_event should emit reasoning revision telemetry."""

    telemetry.record_revision_event(quality_delta=12, addressed=2)

    event, payload = fake_logger[-1]
    assert event == "workflow.reasoning_revision"
    assert payload["workflow"] == "rag"
    assert payload["context"]["quality_delta"] == 12
    assert payload["context"]["addressed"] == 2
