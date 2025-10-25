"""Compatibility wrapper for application-level telemetry facades."""

from __future__ import annotations

from theo.application.facades.telemetry import (
    get_telemetry_provider,
    instrument_workflow,
    log_workflow_event,
    record_counter,
    record_histogram,
    set_span_attribute,
    set_telemetry_provider,
)

__all__ = [
    "get_telemetry_provider",
    "instrument_workflow",
    "log_workflow_event",
    "record_counter",
    "record_histogram",
    "set_span_attribute",
    "set_telemetry_provider",
]
