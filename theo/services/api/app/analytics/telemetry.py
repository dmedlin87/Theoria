"""Helpers for ingesting client-side telemetry."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ..db.feedback import record_feedback_event as persist_feedback_event
from ..db.models import FeedbackEventAction
from ..models.analytics import FeedbackEventPayload, TelemetryBatch

LOGGER = logging.getLogger(__name__)


def record_client_telemetry(batch: TelemetryBatch) -> None:
    """Log client telemetry events for downstream processing."""

    for event in batch.events:
        LOGGER.info(
            "client.telemetry",
            extra={
                "page": batch.page,
                "event": event.event,
                "duration_ms": event.duration_ms,
                "workflow": event.workflow,
                "metadata": event.metadata or {},
            },
        )


def record_feedback_event(
    session: Session,
    *,
    action: FeedbackEventAction | str,
    user_id: str | None = None,
    chat_session_id: str | None = None,
    query: str | None = None,
    document_id: str | None = None,
    passage_id: str | None = None,
    rank: int | None = None,
    score: float | None = None,
    confidence: float | None = None,
) -> None:
    """Persist a feedback event and emit a diagnostic log entry."""

    event = persist_feedback_event(
        session,
        action=action,
        user_id=user_id,
        chat_session_id=chat_session_id,
        query=query,
        document_id=document_id,
        passage_id=passage_id,
        rank=rank,
        score=score,
        confidence=confidence,
    )
    LOGGER.info(
        "client.feedback_event",
        extra={
            "action": event.action.value,
            "user_id": event.user_id,
            "chat_session_id": event.chat_session_id,
            "document_id": event.document_id,
            "passage_id": event.passage_id,
            "rank": event.rank,
            "score": event.score,
            "confidence": event.confidence,
        },
    )


def record_feedback_from_payload(session: Session, payload: FeedbackEventPayload) -> None:
    """Persist feedback supplied via the public analytics endpoint."""

    record_feedback_event(session, **payload.model_dump(exclude_none=True))
