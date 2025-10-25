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


__all__ = [
    "CITATION_DRIFT_EVENTS_METRIC",
    "RAG_CACHE_EVENTS_METRIC",
    "SEARCH_RERANKER_EVENTS_METRIC",
    "TelemetryProvider",
    "WorkflowSpan",
]

