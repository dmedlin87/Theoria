"""Telemetry helpers for workflow instrumentation."""

from __future__ import annotations

import importlib
import logging
import re
from collections.abc import Mapping
from contextlib import contextmanager
from time import perf_counter
from typing import Any, ContextManager, Iterable, Iterator, Protocol, Self, cast


class SpanProtocol(Protocol):
    """Subset of the OpenTelemetry span API used by Theo Engine."""

    def set_attribute(self, key: str, value: Any) -> None:
        ...

    def record_exception(self, exc: BaseException) -> None:
        ...

    def set_status(self, status: Any) -> None:
        ...


class TracerProtocol(Protocol):
    """Tracer interface required for workflow instrumentation."""

    def start_as_current_span(self, name: str) -> ContextManager[SpanProtocol]:
        ...


trace: Any | None
Status: Any | None
StatusCode: Any | None

try:  # pragma: no cover - optional dependency
    trace = importlib.import_module("opentelemetry.trace")
except ImportError:  # pragma: no cover - graceful degradation
    trace = None
    Status = None
    StatusCode = None
else:
    try:  # pragma: no cover - optional dependency
        status_module = importlib.import_module("opentelemetry.trace.status")
    except ImportError:  # pragma: no cover - graceful degradation
        Status = None
        StatusCode = None
    else:
        Status = getattr(status_module, "Status", None)
        StatusCode = getattr(status_module, "StatusCode", None)


Counter: type[Any] | None
Histogram: type[Any] | None

try:  # pragma: no cover - optional dependency
    prometheus_client = importlib.import_module("prometheus_client")
except ImportError:  # pragma: no cover - graceful degradation
    Counter = None
    Histogram = None
else:
    Counter = cast(type[Any], getattr(prometheus_client, "Counter", None))
    Histogram = cast(type[Any], getattr(prometheus_client, "Histogram", None))


class CounterMetric(Protocol):
    def labels(self, **labels: Any) -> Self:
        ...

    def inc(self, amount: float = 1.0) -> None:
        ...


class HistogramMetric(Protocol):
    def labels(self, **labels: Any) -> Self:
        ...

    def observe(self, amount: float) -> None:
        ...


class _NoopSpan:
    def set_attribute(self, *_: Any, **__: Any) -> None:
        return

    def record_exception(self, *_: Any, **__: Any) -> None:
        return

    def set_status(self, *_: Any, **__: Any) -> None:
        return


@contextmanager
def _noop_span(_: str) -> Iterator[SpanProtocol]:
    yield _NoopSpan()


class _NoopTracer:
    def start_as_current_span(self, name: str) -> ContextManager[SpanProtocol]:
        return _noop_span(name)


def _get_tracer(name: str) -> TracerProtocol:
    if trace is None:  # pragma: no cover - optional dependency
        return _NoopTracer()
    return cast(TracerProtocol, trace.get_tracer(name))


LOGGER = logging.getLogger("theo.workflow")

class _NoopMetric:
    def labels(self, **_: Any) -> Self:
        return self

    def inc(self, *_: Any, **__: Any) -> None:
        return

    def observe(self, *_: Any, **__: Any) -> None:
        return


def _build_counter(*args: Any, **kwargs: Any) -> CounterMetric:
    if Counter is None:  # pragma: no cover - metrics disabled
        return cast(CounterMetric, _NoopMetric())
    return cast(CounterMetric, Counter(*args, **kwargs))


def _build_histogram(*args: Any, **kwargs: Any) -> HistogramMetric:
    if Histogram is None:  # pragma: no cover - metrics disabled
        return cast(HistogramMetric, _NoopMetric())
    return cast(HistogramMetric, Histogram(*args, **kwargs))


<<<<<<< HEAD
_METRIC_NAME_PATTERN = re.compile(r"[^a-zA-Z0-9_:]")


def _normalise_metric_name(raw: str) -> str:
    """Transform arbitrary metric identifiers into Prometheus-compatible names."""

    name = raw.strip() if raw else ""
    if not name:
        raise ValueError("metric name must be a non-empty string")
    name = _METRIC_NAME_PATTERN.sub("_", name)
    if not name:
        name = "theo_metric"
    if name[0].isdigit():
        name = f"theo_{name}"
    return name
=======
def _sanitise_metric_name(name: str) -> str:
    """Convert dotted metric names into Prometheus-safe identifiers."""

    sanitized = re.sub(r"[^a-zA-Z0-9_]+", "_", name)
    if not sanitized:
        return "theo_metric"
    if sanitized[0].isdigit():
        sanitized = f"metric_{sanitized}"
    return sanitized
>>>>>>> 9857b44fe48d03f415eac40d68192b0ce0e8d8dd


_COUNTER_CACHE: dict[tuple[str, tuple[str, ...]], CounterMetric] = {}
_HISTOGRAM_CACHE: dict[tuple[str, tuple[str, ...]], HistogramMetric] = {}


<<<<<<< HEAD
def _label_names(labels: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not labels:
        return ()
    return tuple(sorted(labels.keys()))


def _get_counter(metric: str, *, labels: Mapping[str, Any] | None = None) -> CounterMetric:
    normalised = _normalise_metric_name(metric)
    labelnames = _label_names(labels)
    key = (normalised, labelnames)
    cached = _COUNTER_CACHE.get(key)
    if cached is not None:
        return cached
    counter = _build_counter(
        normalised,
        f"Theo dynamic counter for {metric}",
        labelnames=labelnames,
    )
    _COUNTER_CACHE[key] = counter
    return counter


def _get_histogram(
    metric: str,
    *,
    labels: Mapping[str, Any] | None = None,
) -> HistogramMetric:
    normalised = _normalise_metric_name(metric)
    labelnames = _label_names(labels)
    key = (normalised, labelnames)
    cached = _HISTOGRAM_CACHE.get(key)
    if cached is not None:
        return cached
    histogram = _build_histogram(
        normalised,
        f"Theo dynamic histogram for {metric}",
        labelnames=labelnames,
    )
    _HISTOGRAM_CACHE[key] = histogram
    return histogram


def record_counter(metric: str, amount: float = 1.0, **labels: Any) -> None:
    """Increment a named counter metric with optional labels."""

    counter = _get_counter(metric, labels=labels)
    if labels:
        counter.labels(**labels).inc(amount)
    else:
        counter.inc(amount)


def record_histogram(metric: str, amount: float, **labels: Any) -> None:
    """Observe a value for a named histogram metric with optional labels."""

    histogram = _get_histogram(metric, labels=labels)
    if labels:
        histogram.labels(**labels).observe(amount)
    else:
        histogram.observe(amount)
=======
def _get_counter_metric(name: str, label_names: tuple[str, ...]) -> CounterMetric:
    key = (name, label_names)
    metric = _COUNTER_CACHE.get(key)
    if metric is None:
        metric = _build_counter(
            name,
            f"Auto-generated counter for {name}",
            labelnames=label_names,
        )
        _COUNTER_CACHE[key] = metric
    return metric


def _get_histogram_metric(name: str, label_names: tuple[str, ...]) -> HistogramMetric:
    key = (name, label_names)
    metric = _HISTOGRAM_CACHE.get(key)
    if metric is None:
        metric = _build_histogram(
            name,
            f"Auto-generated histogram for {name}",
            labelnames=label_names,
        )
        _HISTOGRAM_CACHE[key] = metric
    return metric


def record_counter(
    metric_name: str, amount: float = 1.0, labels: dict[str, Any] | None = None
) -> None:
    """Increment a Prometheus counter if metrics are enabled."""

    label_values = labels or {}
    label_names = tuple(sorted(label_values))
    metric_id = _sanitise_metric_name(metric_name)
    counter = _get_counter_metric(metric_id, label_names)
    try:
        counter.labels(**label_values).inc(amount)
    except Exception:  # pragma: no cover - defensive
        LOGGER.debug(
            "failed to record counter", extra={"metric": metric_name, "labels": label_values}
        )


def record_histogram(
    metric_name: str, value: float, labels: dict[str, Any] | None = None
) -> None:
    """Observe a value on a Prometheus histogram if metrics are enabled."""

    label_values = labels or {}
    label_names = tuple(sorted(label_values))
    metric_id = _sanitise_metric_name(metric_name)
    histogram = _get_histogram_metric(metric_id, label_names)
    try:
        histogram.labels(**label_values).observe(value)
    except Exception:  # pragma: no cover - defensive
        LOGGER.debug(
            "failed to record histogram", extra={"metric": metric_name, "labels": label_values}
        )
>>>>>>> 9857b44fe48d03f415eac40d68192b0ce0e8d8dd


WORKFLOW_RUNS: CounterMetric = _build_counter(
    "theo_workflow_runs_total",
    "Count of Theo Engine workflow executions by status.",
    labelnames=("workflow", "status"),
)
WORKFLOW_LATENCY: HistogramMetric = _build_histogram(
    "theo_workflow_latency_seconds",
    "Theo Engine workflow execution latency.",
    labelnames=("workflow",),
    buckets=(0.25, 0.5, 1, 2, 4, 8, 16, float("inf")),
)
RAG_CACHE_EVENTS: CounterMetric = _build_counter(
    "theo_rag_cache_events_total",
    "Theo Engine RAG cache events by status.",
    labelnames=("status",),
)
CITATION_DRIFT_EVENTS: CounterMetric = _build_counter(
    "theo_citation_drift_events_total",
    "Theo Engine cached citation validation outcomes.",
    labelnames=("status",),
)
SEARCH_RERANKER_EVENTS: CounterMetric = _build_counter(
    "theo_search_reranker_events_total",
    "Theo Engine reranker lifecycle events.",
    labelnames=("event",),
)


def _serialise_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Mapping):
        serialised_mapping: dict[Any, Any] = {}
        for key, item in value.items():
            serialised_item = _serialise_value(item)
            if serialised_item is not None:
                serialised_mapping[key] = serialised_item
        return serialised_mapping
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        serialised: list[Any] = []
        for item in value:
            serialised_value = _serialise_value(item)
            if serialised_value is not None:
                serialised.append(serialised_value)
        return serialised
    return str(value)


def _serialise_context(context: dict[str, Any]) -> dict[str, Any]:
    serialised: dict[str, Any] = {}
    for key, value in context.items():
        serialised_value = _serialise_value(value)
        if serialised_value is not None:
            serialised[key] = serialised_value
    return serialised


@contextmanager
def instrument_workflow(workflow: str, **attributes: Any) -> Iterator[SpanProtocol]:
    """Context manager recording workflow spans, logs, and metrics."""

    tracer = _get_tracer("theo.workflow")
    serialised_attrs = _serialise_context(attributes)
    LOGGER.info("workflow.start", extra={"workflow": workflow, "context": serialised_attrs})
    start_time = perf_counter()
    status = "success"

    with tracer.start_as_current_span(f"workflow.{workflow}") as span:
        for key, value in serialised_attrs.items():
            span.set_attribute(f"workflow.{key}", value)

        try:
            yield span
        except Exception as exc:  # pragma: no cover - propagated errors
            status = "failed"
            span.record_exception(exc)
            if hasattr(span, "set_status") and Status is not None and StatusCode is not None:
                try:
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                except Exception:  # pragma: no cover - defensive
                    LOGGER.debug("failed to set span status", exc_info=True)
            LOGGER.exception(
                "workflow.failed",
                extra={"workflow": workflow, "context": {**serialised_attrs, "error": str(exc)}},
            )
            raise
        else:
            duration = perf_counter() - start_time
            serialised_attrs["duration_ms"] = round(duration * 1000, 2)
            LOGGER.info(
                "workflow.completed",
                extra={"workflow": workflow, "context": serialised_attrs},
            )
        finally:
            duration = perf_counter() - start_time
            span.set_attribute("workflow.duration_ms", round(duration * 1000, 2))
            WORKFLOW_LATENCY.labels(workflow=workflow).observe(duration)
            WORKFLOW_RUNS.labels(workflow=workflow, status=status).inc()


def set_span_attribute(span: SpanProtocol | None, key: str, value: Any) -> None:
    """Safely set an attribute on the active workflow span."""

    if span is None:
        return
    serialised = _serialise_value(value)
    if serialised is None:
        return
    try:
        span.set_attribute(key, serialised)
    except Exception:  # pragma: no cover - defensive
        LOGGER.debug("failed to set span attribute", extra={"key": key, "value": value})


def log_workflow_event(event: str, *, workflow: str, **context: Any) -> None:
    """Emit a structured log for workflow progress."""

    LOGGER.info(
        event,
        extra={"workflow": workflow, "context": _serialise_context(context)},
    )


__all__ = [
    "instrument_workflow",
    "log_workflow_event",
    "set_span_attribute",
    "record_counter",
    "record_histogram",
    "RAG_CACHE_EVENTS",
    "CITATION_DRIFT_EVENTS",
    "SEARCH_RERANKER_EVENTS",
    "record_counter",
    "record_histogram",
]


def configure_console_tracer() -> None:
    """Configure a console span exporter for local development."""

    if trace is None:  # pragma: no cover - optional dependency
        LOGGER.warning("opentelemetry is not installed; spans will be no-ops")
        return

    provider = trace.get_tracer_provider()
    provider_cls = provider.__class__.__name__
    if provider_cls != "ProxyTracerProvider":  # pragma: no cover - already configured
        return

    try:
        sdk_trace = importlib.import_module("opentelemetry.sdk.trace")
        exporter_module = importlib.import_module("opentelemetry.sdk.trace.export")
    except ImportError:  # pragma: no cover - optional dependency
        LOGGER.warning(
            "opentelemetry-sdk missing; run 'pip install opentelemetry-sdk' to emit spans"
        )
        return

    TracerProvider: type[Any] | None = getattr(sdk_trace, "TracerProvider", None)
    SimpleSpanProcessor: type[Any] | None = getattr(exporter_module, "SimpleSpanProcessor", None)
    ConsoleSpanExporter: type[Any] | None = getattr(exporter_module, "ConsoleSpanExporter", None)
    if (
        TracerProvider is None
        or SimpleSpanProcessor is None
        or ConsoleSpanExporter is None
    ):
        LOGGER.warning("opentelemetry-sdk is installed but missing tracing exports")
        return

    assert TracerProvider is not None
    assert SimpleSpanProcessor is not None
    assert ConsoleSpanExporter is not None

    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(tracer_provider)
    LOGGER.info("Configured console span exporter for Theo workflows")


__all__.append("configure_console_tracer")

