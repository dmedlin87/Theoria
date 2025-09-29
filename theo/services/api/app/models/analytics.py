"""Schemas for analytics and telemetry endpoints."""

from __future__ import annotations

from typing import Any, Sequence

from pydantic import Field

from .base import APIModel


class TelemetryEvent(APIModel):
    """Client-side performance measurement emitted from the web app."""

    event: str = Field(description="Event identifier, e.g. copilot.retrieval.")
    duration_ms: float = Field(
        ge=0.0,
        description="Measured duration of the event in milliseconds.",
    )
    workflow: str | None = Field(
        default=None,
        description="Optional workflow or feature identifier associated with the metric.",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional context key-value pairs supplied by the client.",
    )


class TelemetryBatch(APIModel):
    """Envelope for batching client telemetry events."""

    events: Sequence[TelemetryEvent] = Field(
        default_factory=list,
        description="Ordered list of telemetry events captured on the client side.",
    )
    page: str | None = Field(
        default=None,
        description="Logical page or surface that generated this telemetry batch.",
    )


__all__ = ["TelemetryEvent", "TelemetryBatch"]
