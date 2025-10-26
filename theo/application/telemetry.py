"""Application-level telemetry interfaces."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Mapping, Protocol, runtime_checkable


@runtime_checkable
class WorkflowSpan(Protocol):
    """Minimal span contract used by application workflows."""

    def set_attribute(self, key: str, value: Any) -> None:
        """Attach an attribute to the span."""


@runtime_checkable
class TelemetryProvider(Protocol):
    """Protocol describing telemetry hooks required by the application."""

    def instrument_workflow(self, workflow: str, **attributes: Any) -> AbstractContextManager[WorkflowSpan]:
        """Return a context manager that wraps a workflow execution span."""

    def set_span_attribute(self, span: WorkflowSpan | None, key: str, value: Any) -> None:
        """Safely attach an attribute to a workflow span."""

    def log_workflow_event(self, event: str, *, workflow: str, **context: Any) -> None:
        """Emit a structured telemetry event for workflow progress."""

    def record_counter(
        self, metric_name: str, *, amount: float = 1.0, labels: Mapping[str, Any] | None = None
    ) -> None:
        """Increment a counter metric."""

    def record_histogram(
        self, metric_name: str, *, value: float, labels: Mapping[str, Any] | None = None
    ) -> None:
        """Record a histogram observation."""


RAG_CACHE_EVENTS_METRIC = "theo_rag_cache_events_total"
CITATION_DRIFT_EVENTS_METRIC = "theo_citation_drift_events_total"
SEARCH_RERANKER_EVENTS_METRIC = "theo_search_reranker_events_total"

# Embedding rebuild workflow ----------------------------------------------------
EMBEDDING_REBUILD_BATCH_LATENCY_METRIC = (
    "theo_embedding_rebuild_batch_latency_seconds"
)
EMBEDDING_REBUILD_COMMIT_LATENCY_METRIC = (
    "theo_embedding_rebuild_commit_latency_seconds"
)
EMBEDDING_REBUILD_PROGRESS_METRIC = "theo_embedding_rebuild_processed_total"

# Database query monitoring ------------------------------------------------------
DB_QUERY_LATENCY_METRIC = "theo_db_query_latency_seconds"
DB_QUERY_REQUESTS_METRIC = "theo_db_query_requests_total"
DB_QUERY_ERROR_METRIC = "theo_db_query_errors_total"

# ML inference telemetry --------------------------------------------------------
LLM_INFERENCE_LATENCY_METRIC = "theo_llm_inference_latency_seconds"
LLM_INFERENCE_REQUESTS_METRIC = "theo_llm_inference_requests_total"
LLM_INFERENCE_ERROR_METRIC = "theo_llm_inference_errors_total"


__all__ = [
    "CITATION_DRIFT_EVENTS_METRIC",
    "DB_QUERY_ERROR_METRIC",
    "DB_QUERY_LATENCY_METRIC",
    "DB_QUERY_REQUESTS_METRIC",
    "EMBEDDING_REBUILD_BATCH_LATENCY_METRIC",
    "EMBEDDING_REBUILD_COMMIT_LATENCY_METRIC",
    "EMBEDDING_REBUILD_PROGRESS_METRIC",
    "LLM_INFERENCE_ERROR_METRIC",
    "LLM_INFERENCE_LATENCY_METRIC",
    "LLM_INFERENCE_REQUESTS_METRIC",
    "RAG_CACHE_EVENTS_METRIC",
    "SEARCH_RERANKER_EVENTS_METRIC",
    "TelemetryProvider",
    "WorkflowSpan",
]

