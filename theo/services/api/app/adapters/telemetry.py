"""Telemetry adapter backed by OpenTelemetry and Prometheus clients."""

from __future__ import annotations

import importlib
import logging
import re
from collections.abc import Mapping
from contextlib import AbstractContextManager, contextmanager
from threading import Lock
from time import perf_counter
from typing import Any, ClassVar, Iterable, Iterator, Protocol, Self, cast

from theo.application.telemetry import TelemetryProvider, WorkflowSpan


class _SpanProtocol(Protocol):  # pragma: no cover - structural typing helper
    def set_attribute(self, key: str, value: Any) -> None:
        ...

    def record_exception(self, exc: BaseException) -> None:
        ...

    def set_status(self, status: Any) -> None:
        ...


class _TracerProtocol(Protocol):  # pragma: no cover - structural typing helper
    def start_as_current_span(self, name: str) -> AbstractContextManager[_SpanProtocol]:
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


class _CounterMetric(Protocol):  # pragma: no cover - structural typing helper
    def labels(self, **labels: Any) -> Self:
        ...

    def inc(self, amount: float = 1.0) -> None:
        ...


class _HistogramMetric(Protocol):  # pragma: no cover - structural typing helper
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
def _noop_span(_: str) -> Iterator[_SpanProtocol]:
    yield _NoopSpan()


class _NoopTracer:
    def start_as_current_span(self, name: str) -> AbstractContextManager[_SpanProtocol]:
        return _noop_span(name)


class _NoopMetric:
    def labels(self, **_: Any) -> Self:
        return self

    def inc(self, *_: Any, **__: Any) -> None:
        return

    def observe(self, *_: Any, **__: Any) -> None:
        return


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


def _serialise_context(context: Mapping[str, Any]) -> dict[str, Any]:
    serialised: dict[str, Any] = {}
    for key, value in context.items():
        serialised_value = _serialise_value(value)
        if serialised_value is not None:
            serialised[key] = serialised_value
    return serialised


class ApiTelemetryProvider(TelemetryProvider):
    """Telemetry provider backed by OpenTelemetry and Prometheus."""

    _CACHE_LOCK: ClassVar[Lock] = Lock()
    _COUNTER_CACHE: ClassVar[dict[tuple[str, tuple[str, ...]], _CounterMetric]] = {}
    _HISTOGRAM_CACHE: ClassVar[dict[tuple[str, tuple[str, ...]], _HistogramMetric]] = {}

    def __init__(self) -> None:
        self._logger = logging.getLogger("theo.workflow")
        self._counter_cache = self._COUNTER_CACHE
        self._histogram_cache = self._HISTOGRAM_CACHE
        self._workflow_runs = self._get_counter_metric(
            "theo_workflow_runs_total",
            ("workflow", "status"),
            description="Count of Theo Engine workflow executions by status.",
        )
        self._workflow_latency = self._get_histogram_metric(
            "theo_workflow_latency_seconds",
            ("workflow",),
            description="Theo Engine workflow execution latency.",
            buckets=(0.25, 0.5, 1, 2, 4, 8, 16, float("inf")),
        )

    def configure_console_tracer(self) -> None:
        """Configure a console span exporter for local development."""

        if trace is None:  # pragma: no cover - optional dependency
            self._logger.warning("opentelemetry is not installed; spans will be no-ops")
            return

        provider = trace.get_tracer_provider()
        provider_cls = provider.__class__.__name__
        if provider_cls != "ProxyTracerProvider":  # pragma: no cover - already configured
            return

        try:
            sdk_trace = importlib.import_module("opentelemetry.sdk.trace")
            exporter_module = importlib.import_module("opentelemetry.sdk.trace.export")
        except ImportError:  # pragma: no cover - optional dependency
            self._logger.warning(
                "opentelemetry-sdk missing; run 'pip install opentelemetry-sdk' to emit spans"
            )
            return

        TracerProvider: type[Any] | None = getattr(sdk_trace, "TracerProvider", None)
        SimpleSpanProcessor: type[Any] | None = getattr(exporter_module, "SimpleSpanProcessor", None)
        ConsoleSpanExporter: type[Any] | None = getattr(exporter_module, "ConsoleSpanExporter", None)
        if TracerProvider is None or SimpleSpanProcessor is None or ConsoleSpanExporter is None:
            self._logger.warning("opentelemetry-sdk is installed but missing tracing exports")
            return

        tracer_provider = TracerProvider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(tracer_provider)
        self._logger.info("Configured console span exporter for Theo workflows")

    # TelemetryProvider interface -------------------------------------------------

    def instrument_workflow(self, workflow: str, **attributes: Any) -> AbstractContextManager[WorkflowSpan]:
        tracer = self._get_tracer("theo.workflow")
        serialised_attrs = _serialise_context(attributes)
        self._logger.info("workflow.start", extra={"workflow": workflow, "context": serialised_attrs})
        start_time = perf_counter()
        status = "success"

        @contextmanager
        def _span_context() -> Iterator[WorkflowSpan]:
            with tracer.start_as_current_span(f"workflow.{workflow}") as span:
                for key, value in serialised_attrs.items():
                    span.set_attribute(f"workflow.{key}", value)

                try:
                    yield cast(WorkflowSpan, span)
                except Exception as exc:  # pragma: no cover - propagated errors
                    nonlocal status
                    status = "failed"
                    span.record_exception(exc)
                    if hasattr(span, "set_status") and Status is not None and StatusCode is not None:
                        try:
                            span.set_status(Status(StatusCode.ERROR, str(exc)))
                        except Exception:  # pragma: no cover - defensive
                            self._logger.debug("failed to set span status", exc_info=True)
                    self._logger.exception(
                        "workflow.failed",
                        extra={"workflow": workflow, "context": {**serialised_attrs, "error": str(exc)}},
                    )
                    raise
                else:
                    duration = perf_counter() - start_time
                    serialised_attrs["duration_ms"] = round(duration * 1000, 2)
                    self._logger.info(
                        "workflow.completed",
                        extra={"workflow": workflow, "context": serialised_attrs},
                    )
                finally:
                    duration = perf_counter() - start_time
                    span.set_attribute("workflow.duration_ms", round(duration * 1000, 2))
                    self._workflow_latency.labels(workflow=workflow).observe(duration)
                    self._workflow_runs.labels(workflow=workflow, status=status).inc()

        return _span_context()

    def set_span_attribute(self, span: WorkflowSpan | None, key: str, value: Any) -> None:
        if span is None:
            return
        serialised = _serialise_value(value)
        if serialised is None:
            return
        try:
            cast(_SpanProtocol, span).set_attribute(key, serialised)
        except Exception:  # pragma: no cover - defensive
            self._logger.debug("failed to set span attribute", extra={"key": key, "value": value})

    def log_workflow_event(self, event: str, *, workflow: str, **context: Any) -> None:
        self._logger.info(event, extra={"workflow": workflow, "context": _serialise_context(context)})

    def record_counter(
        self, metric_name: str, *, amount: float = 1.0, labels: Mapping[str, Any] | None = None
    ) -> None:
        label_values = labels or {}
        label_names = tuple(sorted(label_values))
        metric_id = self._sanitise_metric_name(metric_name)
        counter = self._get_counter_metric(metric_id, label_names)
        try:
            counter.labels(**label_values).inc(amount)
        except Exception:  # pragma: no cover - defensive
            self._logger.debug(
                "failed to record counter", extra={"metric": metric_name, "labels": label_values}
            )

    def record_histogram(
        self, metric_name: str, *, value: float, labels: Mapping[str, Any] | None = None
    ) -> None:
        label_values = labels or {}
        label_names = tuple(sorted(label_values))
        metric_id = self._sanitise_metric_name(metric_name)
        histogram = self._get_histogram_metric(metric_id, label_names)
        try:
            histogram.labels(**label_values).observe(value)
        except Exception:  # pragma: no cover - defensive
            self._logger.debug(
                "failed to record histogram", extra={"metric": metric_name, "labels": label_values}
            )

    # Internal helpers -----------------------------------------------------------

    def _get_tracer(self, name: str) -> _TracerProtocol:
        if trace is None:  # pragma: no cover - optional dependency
            return _NoopTracer()
        return cast(_TracerProtocol, trace.get_tracer(name))

    def _sanitise_metric_name(self, name: str) -> str:
        sanitized = re.sub(r"[^a-zA-Z0-9_]+", "_", name)
        if not sanitized:
            return "theo_metric"
        if sanitized[0].isdigit():
            sanitized = f"metric_{sanitized}"
        return sanitized

    def _build_counter(self, *args: Any, **kwargs: Any) -> _CounterMetric:
        if Counter is None:  # pragma: no cover - metrics disabled
            return cast(_CounterMetric, _NoopMetric())
        return cast(_CounterMetric, Counter(*args, **kwargs))

    def _build_histogram(self, *args: Any, **kwargs: Any) -> _HistogramMetric:
        if Histogram is None:  # pragma: no cover - metrics disabled
            return cast(_HistogramMetric, _NoopMetric())
        return cast(_HistogramMetric, Histogram(*args, **kwargs))

    def _get_counter_metric(
        self,
        name: str,
        label_names: tuple[str, ...],
        *,
        description: str | None = None,
    ) -> _CounterMetric:
        key = (name, label_names)
        metric = self._counter_cache.get(key)
        if metric is not None:
            return metric
        with self._CACHE_LOCK:
            metric = self._counter_cache.get(key)
            if metric is None:
                metric = self._build_counter(
                    name,
                    description or f"Auto-generated counter for {name}",
                    labelnames=label_names,
                )
                self._counter_cache[key] = metric
        return cast(_CounterMetric, metric)

    def _get_histogram_metric(
        self,
        name: str,
        label_names: tuple[str, ...],
        *,
        description: str | None = None,
        buckets: tuple[float, ...] | None = None,
    ) -> _HistogramMetric:
        key = (name, label_names)
        metric = self._histogram_cache.get(key)
        if metric is not None:
            return metric
        with self._CACHE_LOCK:
            metric = self._histogram_cache.get(key)
            if metric is None:
                histogram_kwargs: dict[str, Any] = {"labelnames": label_names}
                if buckets is not None:
                    histogram_kwargs["buckets"] = buckets
                metric = self._build_histogram(
                    name,
                    description or f"Auto-generated histogram for {name}",
                    **histogram_kwargs,
                )
                self._histogram_cache[key] = metric
        return cast(_HistogramMetric, metric)


__all__ = ["ApiTelemetryProvider"]

