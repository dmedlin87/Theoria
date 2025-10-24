"""Telemetry helpers for the guardrailed RAG chat workflow."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from opentelemetry import trace

from ...telemetry import log_workflow_event

_RAG_TRACER = trace.get_tracer("theo.rag")


@contextmanager
def generation_span(
    candidate_name: str,
    candidate_model: str,
    *,
    cache_status: str,
    cache_key_suffix: str | None,
    prompt: str,
) -> Iterator[Any]:
    """Record telemetry for a routed generation attempt."""

    with _RAG_TRACER.start_as_current_span("rag.execute_generation") as span:
        span.set_attribute("rag.candidate", candidate_name)
        span.set_attribute("rag.model_label", candidate_model)
        span.set_attribute("rag.cache_status", cache_status)
        if cache_key_suffix:
            span.set_attribute("rag.cache_key_suffix", cache_key_suffix)
        span.set_attribute("rag.prompt_tokens", max(len(prompt) // 4, 0))
        yield span


def record_generation_result(span: Any, *, latency_ms: int | None, completion: str | None) -> None:
    """Attach generation result metadata to the active span."""

    if span is None:
        return
    if latency_ms is not None:
        span.set_attribute("rag.latency_ms", latency_ms)
    if completion:
        span.set_attribute("rag.completion_tokens", max(len(completion) // 4, 0))


def set_final_cache_status(span: Any, cache_status: str) -> None:
    """Record the final cache outcome on the span."""

    if span is None:
        return
    span.set_attribute("rag.guardrails_cache_final", cache_status)


def record_validation_event(
    status: str,
    *,
    cache_status: str,
    cache_key_suffix: str | None,
    citation_count: int | None,
    cited_indices: list[int] | None,
) -> None:
    """Log guardrail validation telemetry for the workflow."""

    log_workflow_event(
        "workflow.guardrails_validation",
        workflow="rag",
        status=status,
        cache_status=cache_status,
        cache_key_suffix=cache_key_suffix,
        citation_count=citation_count,
        cited_indices=cited_indices,
    )


def record_answer_event(*, citation_count: int) -> None:
    """Log that a guardrailed answer was produced."""

    log_workflow_event(
        "workflow.answer_composed",
        workflow="chat",
        citations=citation_count,
    )


def record_passages_retrieved(*, result_count: int) -> None:
    """Log telemetry when passages are retrieved for chat."""

    log_workflow_event(
        "workflow.passages_retrieved",
        workflow="chat",
        result_count=result_count,
    )


def record_revision_event(*, quality_delta: float | None, addressed: int | None) -> None:
    """Log telemetry for a successful reasoning revision."""

    log_workflow_event(
        "workflow.reasoning_revision",
        workflow="rag",
        status="applied",
        quality_delta=quality_delta,
        addressed=addressed,
    )


__all__ = [
    "generation_span",
    "record_passages_retrieved",
    "record_answer_event",
    "record_generation_result",
    "record_revision_event",
    "record_validation_event",
    "set_final_cache_status",
]
