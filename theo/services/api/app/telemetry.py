"""Telemetry helpers for workflow instrumentation."""

from __future__ import annotations

import importlib
import logging
from contextlib import contextmanager
from time import perf_counter
from typing import Any, ContextManager, Iterable, Iterator, Protocol, cast


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


try:  # pragma: no cover - optional dependency
    prometheus_client = importlib.import_module("prometheus_client")
except ImportError:  # pragma: no cover - graceful degradation
    Counter = Histogram = None  # type: ignore[assignment]
else:
    Counter = cast(Any, getattr(prometheus_client, "Counter", None))
    Histogram = cast(Any, getattr(prometheus_client, "Histogram", None))


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

if Counter is None or Histogram is None:  # pragma: no cover - metrics disabled

    class _NoopMetric:
        def labels(self, **_: Any) -> "_NoopMetric":
            return self

        def inc(self, *_: Any, **__: Any) -> None:
            return

        def observe(self, *_: Any, **__: Any) -> None:
            return

    WORKFLOW_RUNS = _NoopMetric()
    WORKFLOW_LATENCY = _NoopMetric()
else:
    WORKFLOW_RUNS = Counter(
        "theo_workflow_runs_total",
        "Count of Theo Engine workflow executions by status.",
        labelnames=("workflow", "status"),
    )
    WORKFLOW_LATENCY = Histogram(
        "theo_workflow_latency_seconds",
        "Theo Engine workflow execution latency.",
        labelnames=("workflow",),
        buckets=(0.25, 0.5, 1, 2, 4, 8, 16, float("inf")),
    )


def _serialise_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, bool, int, float)):
        return value
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

