"""Helpers for working with OpenTelemetry trace context."""

from __future__ import annotations

from typing import Any, Dict

try:  # pragma: no cover - optional dependency
    from opentelemetry.trace import get_current_span
except ImportError:  # pragma: no cover - graceful degradation
    get_current_span = None  # type: ignore[assignment]

TRACEPARENT_HEADER_NAME = "traceparent"
TRACE_ID_HEADER_NAME = "x-trace-id"


def _get_span_context() -> Any | None:
    if get_current_span is None:  # pragma: no cover - optional dependency
        return None
    try:
        span = get_current_span()
    except Exception:  # pragma: no cover - defensive
        return None
    if span is None:
        return None
    try:
        context = span.get_span_context()
    except Exception:  # pragma: no cover - defensive
        return None
    return context


def get_current_trace_id() -> str | None:
    """Return the active trace identifier if a span is available."""

    context = _get_span_context()
    if context is None:
        return None
    trace_id = getattr(context, "trace_id", 0)
    if not trace_id:
        return None
    try:
        formatted = format(int(trace_id), "032x")
    except Exception:  # pragma: no cover - defensive
        return None
    return formatted


def get_current_traceparent() -> str | None:
    """Return a W3C traceparent header value for the active span."""

    context = _get_span_context()
    if context is None:
        return None
    trace_id = getattr(context, "trace_id", 0)
    span_id = getattr(context, "span_id", 0)
    trace_flags = getattr(context, "trace_flags", 0)
    if not trace_id or not span_id:
        return None
    try:
        trace_id_hex = format(int(trace_id), "032x")
        span_id_hex = format(int(span_id), "016x")
        trace_flags_int = int(trace_flags)
        trace_flags_hex = format(trace_flags_int, "02x")
    except Exception:  # pragma: no cover - defensive
        return None
    return f"00-{trace_id_hex}-{span_id_hex}-{trace_flags_hex}"


def get_current_trace_headers() -> Dict[str, str]:
    """Return trace headers suitable for attaching to an HTTP response."""

    headers: Dict[str, str] = {}
    traceparent = get_current_traceparent()
    if traceparent:
        headers[TRACEPARENT_HEADER_NAME] = traceparent
    trace_id = get_current_trace_id()
    if trace_id:
        headers[TRACE_ID_HEADER_NAME] = trace_id
    return headers


__all__ = [
    "TRACEPARENT_HEADER_NAME",
    "TRACE_ID_HEADER_NAME",
    "get_current_trace_headers",
    "get_current_trace_id",
    "get_current_traceparent",
]
