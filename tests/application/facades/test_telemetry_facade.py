from contextlib import AbstractContextManager, contextmanager
from typing import Any

import pytest

from theo.application.facades import telemetry as telemetry_facade
from theo.application.telemetry import TelemetryProvider, WorkflowSpan


class _Span:
    def __init__(self) -> None:
        self.attributes: list[tuple[str, object]] = []

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes.append((key, value))


class _Provider(TelemetryProvider):
    def __init__(self) -> None:
        self.instrumented: list[tuple[str, dict[str, object]]] = []
        self.span_calls: list[tuple[str, object]] = []
        self.events: list[tuple[str, dict[str, object]]] = []
        self.counters: list[tuple[str, float, dict[str, object]]] = []
        self.histograms: list[tuple[str, float, dict[str, object]]] = []

    @contextmanager
    def instrument_workflow(self, workflow: str, **attributes: Any) -> AbstractContextManager[WorkflowSpan]:
        span = _Span()
        self.instrumented.append((workflow, dict(attributes)))
        yield span  # type: ignore[misc]

    def set_span_attribute(self, span: WorkflowSpan | None, key: str, value: Any) -> None:
        if span is not None:
            span.set_attribute(key, value)
        else:
            self.span_calls.append((key, value))

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

    def record_histogram(
        self,
        metric_name: str,
        *,
        value: float,
        labels: dict[str, Any] | None = None,
    ) -> None:
        self.histograms.append((metric_name, value, dict(labels or {})))


@pytest.fixture(autouse=True)
def _reset_provider() -> None:
    previous = getattr(telemetry_facade, "_provider", None)
    telemetry_facade._provider = None  # type: ignore[attr-defined]
    try:
        yield
    finally:
        telemetry_facade._provider = previous  # type: ignore[attr-defined]


def test_get_provider_requires_configuration() -> None:
    with pytest.raises(RuntimeError):
        telemetry_facade.get_telemetry_provider()


def test_facade_delegates_to_provider() -> None:
    provider = _Provider()
    telemetry_facade.set_telemetry_provider(provider)

    with telemetry_facade.instrument_workflow("workflow", attempt=1) as span:
        telemetry_facade.set_span_attribute(span, "key", "value")

    telemetry_facade.log_workflow_event("completed", workflow="workflow", status="ok")
    telemetry_facade.record_counter("metric", amount=2, labels={"source": "unit"})
    telemetry_facade.record_histogram("hist", value=0.5, labels={"kind": "unit"})

    assert telemetry_facade.get_telemetry_provider() is provider
    assert provider.instrumented == [("workflow", {"attempt": 1})]
    assert provider.events == [("completed", {"workflow": "workflow", "status": "ok"})]
    assert provider.counters == [("metric", 2, {"source": "unit"})]
    assert provider.histograms == [("hist", 0.5, {"kind": "unit"})]
    assert provider.instrumented[0][0] == "workflow"


def test_facade_handles_missing_provider_gracefully() -> None:
    with telemetry_facade.instrument_workflow("noop") as span:
        telemetry_facade.set_span_attribute(span, "ignored", True)
    telemetry_facade.log_workflow_event("noop", workflow="noop")
    telemetry_facade.record_counter("metric")
    telemetry_facade.record_histogram("hist", value=1.0)
