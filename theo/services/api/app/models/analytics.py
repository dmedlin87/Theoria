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


class FeedbackEventPayload(APIModel):
    """Request body describing a user feedback interaction."""

    action: str = Field(
        description="Categorical label describing the feedback interaction.",
    )
    user_id: str | None = Field(
        default=None,
        description="Identifier of the user submitting the feedback, if available.",
    )
    chat_session_id: str | None = Field(
        default=None,
        description="Associated conversational session identifier, when relevant.",
    )
    query: str | None = Field(
        default=None,
        description="Original user query or prompt that produced this feedback event.",
    )
    document_id: str | None = Field(
        default=None,
        description="Identifier of the cited document involved in the interaction.",
    )
    passage_id: str | None = Field(
        default=None,
        description="Identifier of the cited passage involved in the interaction.",
    )
    rank: int | None = Field(
        default=None,
        ge=0,
        description="Zero-based rank of the cited item within the retrieval results.",
    )
    score: float | None = Field(
        default=None,
        description="Retrieval score for the cited item, if available.",
    )
    confidence: float | None = Field(
        default=None,
        description="System confidence assigned to the citation, when supplied.",
    )


__all__ = ["TelemetryEvent", "TelemetryBatch", "FeedbackEventPayload"]
