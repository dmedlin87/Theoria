"""Observability helpers for repository instrumentation."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager, nullcontext
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Iterator, Mapping

from .facades.telemetry import (
    instrument_workflow,
    record_counter,
    record_histogram,
    set_span_attribute,
)

REPOSITORY_LATENCY_METRIC = "theo_repository_latency_seconds"
REPOSITORY_RESULT_METRIC = "theo_repository_results_total"


@dataclass(slots=True)
class RepositoryCallTrace:
    """State manager for repository instrumentation."""

    repository: str
    operation: str
    span: Any

    def set_attribute(self, key: str, value: Any) -> None:
        """Attach an attribute scoped to the repository span."""

        set_span_attribute(self.span, f"repository.{key}", value)

    def record_result_count(self, count: int) -> None:
        """Record the number of entities returned by the repository call."""

        labels = {"repository": self.repository, "operation": self.operation}
        record_counter(REPOSITORY_RESULT_METRIC, amount=count, labels=labels)
        self.set_attribute("result_count", count)


class _NullRepositoryCallTrace:
    """Fallback trace that disables telemetry operations."""

    __slots__ = ("repository", "operation")

    def __init__(self, *, repository: str, operation: str) -> None:
        self.repository = repository
        self.operation = operation

    def set_attribute(self, key: str, value: Any) -> None:  # noqa: D401 - mimic RepositoryCallTrace
        """No-op attribute setter when telemetry is disabled."""

    def record_result_count(self, count: int) -> None:  # noqa: D401 - mimic RepositoryCallTrace
        """No-op result recorder when telemetry is disabled."""


@contextmanager
def trace_repository_call(
    repository: str,
    operation: str,
    *,
    attributes: Mapping[str, Any] | None = None,
) -> Iterator[RepositoryCallTrace]:
    """Instrument a repository method with tracing and metrics."""

    enriched_attributes = {"repository": repository, "operation": operation}
    if attributes:
        enriched_attributes.update(attributes)

    workflow_name = f"repository.{repository}.{operation}"

    with ExitStack() as stack:
        try:
            span = stack.enter_context(
                instrument_workflow(workflow_name, **enriched_attributes)
            )
        except RuntimeError:
            span = stack.enter_context(nullcontext(None))
            telemetry_enabled = False
        else:
            telemetry_enabled = True

        start_time = perf_counter() if telemetry_enabled else None

        if telemetry_enabled:
            trace: RepositoryCallTrace | _NullRepositoryCallTrace = RepositoryCallTrace(
                repository=repository,
                operation=operation,
                span=span,
            )

            trace.set_attribute("name", repository)
            trace.set_attribute("operation", operation)
            for key, value in (attributes or {}).items():
                trace.set_attribute(key, value)
        else:
            trace = _NullRepositoryCallTrace(repository=repository, operation=operation)

        try:
            yield trace
        except Exception:
            if telemetry_enabled:
                trace.set_attribute("status", "failed")
            raise
        else:
            if telemetry_enabled:
                trace.set_attribute("status", "success")
        finally:
            if telemetry_enabled and start_time is not None:
                duration = perf_counter() - start_time
                trace.set_attribute("duration_ms", round(duration * 1000, 2))
                record_histogram(
                    REPOSITORY_LATENCY_METRIC,
                    value=duration,
                    labels={"repository": repository, "operation": operation},
                )


__all__ = [
    "REPOSITORY_LATENCY_METRIC",
    "REPOSITORY_RESULT_METRIC",
    "RepositoryCallTrace",
    "trace_repository_call",
]
