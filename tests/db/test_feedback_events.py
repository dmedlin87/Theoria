"""Tests for feedback event persistence helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.core.database import Base
from theo.services.api.app.db.feedback import record_feedback_event
from theo.services.api.app.db.models import FeedbackEvent, FeedbackEventAction


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )
    db_session = TestingSession()
    try:
        yield db_session
    finally:
        db_session.close()
        engine.dispose()


def test_record_feedback_event_persists_and_defaults(session: Session) -> None:
    event = record_feedback_event(
        session,
        user_id="user-123",
        chat_session_id="chat-456",
        query="Who wrote the letter?",
        document_id="doc-789",
        passage_id="passage-321",
        action="view",
        rank=1,
        score=0.87,
        confidence=0.42,
    )
    session.commit()

    stored = session.get(FeedbackEvent, event.id)
    assert stored is not None
    assert stored.user_id == "user-123"
    assert stored.chat_session_id == "chat-456"
    assert stored.document_id == "doc-789"
    assert stored.passage_id == "passage-321"
    assert stored.action is FeedbackEventAction.VIEW
    assert stored.rank == 1
    assert stored.score == pytest.approx(0.87)
    assert stored.confidence == pytest.approx(0.42)
    assert stored.created_at is not None


def test_record_feedback_event_accepts_enum(session: Session) -> None:
    event = record_feedback_event(
        session,
        action=FeedbackEventAction.LIKE,
        query="Show me more",  # ensures optional fields accepted
    )
    session.commit()

    stored = session.get(FeedbackEvent, event.id)
    assert stored is not None
    assert stored.action is FeedbackEventAction.LIKE


def test_record_feedback_event_rejects_invalid_action(session: Session) -> None:
    with pytest.raises(ValueError):
        record_feedback_event(session, action="invalid-action")
