from contextlib import contextmanager

from theo.application.telemetry import (
    CITATION_DRIFT_EVENTS_METRIC,
    RAG_CACHE_EVENTS_METRIC,
    SEARCH_RERANKER_EVENTS_METRIC,
    TelemetryProvider,
    WorkflowSpan,
)


class _SpanImpl:
    def __init__(self) -> None:
        self.attributes: dict[str, object] = {}

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


class _TelemetryProviderImpl:
    def __init__(self) -> None:
        self.instrumented: list[tuple[str, dict[str, object]]] = []
        self.events: list[tuple[str, dict[str, object]]] = []
        self.counters: list[tuple[str, float, dict[str, object]]] = []
        self.histograms: list[tuple[str, float, dict[str, object]]] = []

    @contextmanager
    def instrument_workflow(self, workflow: str, **attributes: object):
        span = _SpanImpl()
        self.instrumented.append((workflow, dict(attributes)))
        yield span  # type: ignore[misc]

    def set_span_attribute(self, span: WorkflowSpan | None, key: str, value: object) -> None:
        if span is not None:
            span.set_attribute(key, value)

    def log_workflow_event(self, event: str, *, workflow: str, **context: object) -> None:
        self.events.append((event, {"workflow": workflow, **context}))

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


def test_telemetry_provider_protocol() -> None:
    provider = _TelemetryProviderImpl()

    assert isinstance(provider, TelemetryProvider)

    with provider.instrument_workflow("workflow", user="alice") as span:
        provider.set_span_attribute(span, "key", "value")

    assert provider.instrumented[0][0] == "workflow"
    assert provider.instrumented[0][1] == {"user": "alice"}

    provider.log_workflow_event("processed", workflow="workflow", status="ok")
    provider.record_counter(RAG_CACHE_EVENTS_METRIC, amount=2, labels={"source": "cache"})
    provider.record_histogram(
        SEARCH_RERANKER_EVENTS_METRIC,
        value=0.42,
        labels={"model": "reranker"},
    )

    assert provider.events == [("processed", {"workflow": "workflow", "status": "ok"})]
    assert provider.counters == [(RAG_CACHE_EVENTS_METRIC, 2, {"source": "cache"})]
    assert provider.histograms == [
        (SEARCH_RERANKER_EVENTS_METRIC, 0.42, {"model": "reranker"})
    ]
    assert isinstance(CITATION_DRIFT_EVENTS_METRIC, str)
