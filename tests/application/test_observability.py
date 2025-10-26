"""Unit tests for application observability helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest

from theo.application.observability import (
    REPOSITORY_LATENCY_METRIC,
    REPOSITORY_RESULT_METRIC,
    trace_repository_call,
)
from theo.application.facades import telemetry as telemetry_facade


class _FakeSpan:
    def __init__(self, recorder: list[tuple[str, object]]):
        self._recorder = recorder

    def set_attribute(self, key: str, value: object) -> None:
        self._recorder.append((key, value))


class _FakeTelemetryProvider:
    def __init__(self) -> None:
        self.instrumented: list[tuple[str, dict[str, object]]] = []
        self.counters: list[tuple[str, float, dict[str, object]]] = []
        self.histograms: list[tuple[str, float, dict[str, object]]] = []
        self.span_attributes: list[tuple[str, object]] = []

    @contextmanager
    def instrument_workflow(self, workflow: str, **attributes: object):
        span = _FakeSpan(self.span_attributes)
        self.instrumented.append((workflow, dict(attributes)))
        yield span  # type: ignore[misc]

    def set_span_attribute(self, span: Any, key: str, value: object) -> None:
        if span is None:
            return
        try:
            span.set_attribute(key, value)  # type: ignore[call-arg]
        except Exception:  # pragma: no cover - defensive guard for future span types
            self.span_attributes.append((key, value))

    def log_workflow_event(self, event: str, *, workflow: str, **context: object) -> None:
        self.instrumented.append((f"event:{event}", {"workflow": workflow, **context}))

    def record_counter(
        self,
        metric_name: str,
        *,
        amount: float = 1.0,
        labels: dict[str, object] | None = None,
    ) -> None:
        self.counters.append((metric_name, amount, dict(labels or {})))

    def record_histogram(
        self,
        metric_name: str,
        *,
        value: float,
        labels: dict[str, object] | None = None,
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


def test_trace_repository_call_records_metrics_and_attributes() -> None:
    provider = _FakeTelemetryProvider()
    telemetry_facade.set_telemetry_provider(provider)

    with trace_repository_call(
        "document",
        "list",
        attributes={"user_id": "abc"},
    ) as trace:
        trace.record_result_count(3)
        trace.set_attribute("extra", "value")

    assert provider.instrumented[0][0] == "repository.document.list"
    assert provider.instrumented[0][1]["user_id"] == "abc"

    counter = provider.counters[-1]
    assert counter[0] == REPOSITORY_RESULT_METRIC
    assert counter[1] == 3
    assert counter[2] == {"repository": "document", "operation": "list"}

    histogram = provider.histograms[-1]
    assert histogram[0] == REPOSITORY_LATENCY_METRIC
    assert histogram[2] == {"repository": "document", "operation": "list"}

    attr_keys = {key for key, _ in provider.span_attributes}
    assert {"repository.name", "repository.operation", "repository.result_count", "repository.extra", "repository.status"}.issubset(attr_keys)


def test_trace_repository_call_marks_failure() -> None:
    provider = _FakeTelemetryProvider()
    telemetry_facade.set_telemetry_provider(provider)

    with pytest.raises(RuntimeError):
        with trace_repository_call("document", "explode"):
            raise RuntimeError("boom")

    failure_attrs = [value for key, value in provider.span_attributes if key == "repository.status"]
    assert failure_attrs[-1] == "failed"
    assert provider.histograms[-1][0] == REPOSITORY_LATENCY_METRIC


def test_trace_repository_call_without_provider_is_noop() -> None:
    with trace_repository_call("document", "list") as trace:
        trace.record_result_count(1)
        trace.set_attribute("ignored", True)

    assert getattr(trace, "repository") == "document"
    assert getattr(trace, "operation") == "list"


def test_trace_repository_call_handles_instrumentation_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailingProvider:
        def instrument_workflow(self, workflow: str, **attributes: object):  # pragma: no cover - context manager protocol
            raise RuntimeError("telemetry disabled")

        def set_span_attribute(self, span: object, key: str, value: object) -> None:
            raise AssertionError("should not be called when span missing")

        def log_workflow_event(self, event: str, *, workflow: str, **context: object) -> None:
            raise AssertionError("no logging expected")

        def record_counter(self, metric_name: str, *, amount: float = 1.0, labels: dict[str, object] | None = None) -> None:
            raise AssertionError("no counters expected")

        def record_histogram(self, metric_name: str, *, value: float, labels: dict[str, object] | None = None) -> None:
            raise AssertionError("no histograms expected")

    telemetry_facade.set_telemetry_provider(_FailingProvider())

    with trace_repository_call("document", "noop") as trace:
        assert isinstance(trace, object)
        trace.set_attribute("ignored", "value")
