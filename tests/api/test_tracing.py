"""Tests for OpenTelemetry tracing helper utilities."""
from __future__ import annotations

from typing import Any

from theo.services.api.app import tracing


class _StubSpan:
    def __init__(self, context: Any):
        self._context = context

    def get_span_context(self):  # pragma: no cover - exercised via helper
        return self._context


class _ExplodingSpan:
    def get_span_context(self):  # pragma: no cover - exercised via helper
        raise RuntimeError("boom")


def _install_span(monkeypatch, span):
    monkeypatch.setattr(tracing, "_GET_CURRENT_SPAN", lambda: span)


def test_trace_helpers_happy_path(monkeypatch):
    trace_id = 0x1234567890ABCDEF1234567890ABCDEF
    span_id = 0x89ABCDEF01234567
    trace_flags = 0x5A
    context = type(
        "StubContext",
        (),
        {
            "trace_id": trace_id,
            "span_id": span_id,
            "trace_flags": trace_flags,
        },
    )()
    span = _StubSpan(context)
    _install_span(monkeypatch, span)

    expected_trace_id = format(trace_id, "032x")
    expected_span_id = format(span_id, "016x")
    expected_flags = format(trace_flags, "02x")

    assert tracing.get_current_trace_id() == expected_trace_id

    expected_traceparent = f"00-{expected_trace_id}-{expected_span_id}-{expected_flags}"
    assert tracing.get_current_traceparent() == expected_traceparent

    headers = tracing.get_current_trace_headers()
    assert headers == {
        tracing.TRACEPARENT_HEADER_NAME: expected_traceparent,
        tracing.TRACE_ID_HEADER_NAME: expected_trace_id,
    }


def test_trace_helpers_return_none_when_context_missing(monkeypatch):
    class _MissingContextSpan:
        def get_span_context(self):  # pragma: no cover - exercised via helper
            return None

    _install_span(monkeypatch, _MissingContextSpan())

    assert tracing.get_current_trace_id() is None
    assert tracing.get_current_traceparent() is None
    assert tracing.get_current_trace_headers() == {}


def test_trace_helpers_return_none_with_zero_identifiers(monkeypatch):
    context = type(
        "ZeroContext",
        (),
        {
            "trace_id": 0,
            "span_id": 0,
            "trace_flags": 0,
        },
    )()
    span = _StubSpan(context)
    _install_span(monkeypatch, span)

    assert tracing.get_current_trace_id() is None
    assert tracing.get_current_traceparent() is None
    assert tracing.get_current_trace_headers() == {}


def test_trace_helpers_handle_span_context_errors(monkeypatch):
    _install_span(monkeypatch, _ExplodingSpan())

    assert tracing.get_current_trace_id() is None
    assert tracing.get_current_traceparent() is None
    assert tracing.get_current_trace_headers() == {}
