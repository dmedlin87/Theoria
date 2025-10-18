"""Helpers for persisting feedback events."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from theo.services.api.app.persistence_models import FeedbackEvent, FeedbackEventAction


def record_feedback_event(
    session: Session,
    *,
    user_id: str | None = None,
    chat_session_id: str | None = None,
    query: str | None = None,
    document_id: str | None = None,
    passage_id: str | None = None,
    action: FeedbackEventAction | str,
    rank: int | None = None,
    score: float | None = None,
    confidence: float | None = None,
    created_at: datetime | None = None,
) -> FeedbackEvent:
    """Persist a feedback event, validating the provided action value."""

    try:
        action_value = (
            action
            if isinstance(action, FeedbackEventAction)
            else FeedbackEventAction(action)
        )
    except ValueError as exc:
        raise ValueError(f"Invalid feedback action: {action!r}") from exc

    event = FeedbackEvent(
        user_id=user_id,
        chat_session_id=chat_session_id,
        query=query,
        document_id=document_id,
        passage_id=passage_id,
        action=action_value,
        rank=rank,
        score=score,
        confidence=confidence,
        created_at=created_at or datetime.now(UTC),
    )
    session.add(event)
    session.flush()
    return event
