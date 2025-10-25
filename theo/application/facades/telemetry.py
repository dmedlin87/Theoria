"""Facade exposing telemetry operations to the application layer."""

from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager
from typing import Any, Mapping, Optional

from ..telemetry import TelemetryProvider, WorkflowSpan

_provider: TelemetryProvider | None = None


def set_telemetry_provider(provider: TelemetryProvider) -> None:
    """Register the active telemetry provider."""

    global _provider
    _provider = provider


def get_telemetry_provider() -> TelemetryProvider:
    """Return the currently registered telemetry provider."""

    if _provider is None:
        raise RuntimeError("Telemetry provider has not been configured")
    return _provider


@contextmanager
def instrument_workflow(workflow: str, **attributes: Any) -> AbstractContextManager[WorkflowSpan]:
    """Proxy to :meth:`TelemetryProvider.instrument_workflow`."""

    with get_telemetry_provider().instrument_workflow(workflow, **attributes) as span:
        yield span


def set_span_attribute(span: WorkflowSpan | None, key: str, value: Any) -> None:
    """Safely attach an attribute to a workflow span."""

    get_telemetry_provider().set_span_attribute(span, key, value)


def log_workflow_event(event: str, *, workflow: str, **context: Any) -> None:
    """Emit a structured telemetry event."""

    get_telemetry_provider().log_workflow_event(event, workflow=workflow, **context)


def record_counter(metric_name: str, *, amount: float = 1.0, labels: Optional[Mapping[str, Any]] = None) -> None:
    """Increment a counter metric."""

    get_telemetry_provider().record_counter(metric_name, amount=amount, labels=labels)


def record_histogram(metric_name: str, *, value: float, labels: Optional[Mapping[str, Any]] = None) -> None:
    """Record a histogram observation."""

    get_telemetry_provider().record_histogram(metric_name, value=value, labels=labels)


__all__ = [
    "get_telemetry_provider",
    "instrument_workflow",
    "log_workflow_event",
    "record_counter",
    "record_histogram",
    "set_span_attribute",
    "set_telemetry_provider",
]

