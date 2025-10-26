"""Tests for the SQLAlchemy chat session repository."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from theo.adapters.persistence.chat_repository import SQLAlchemyChatSessionRepository
from theo.adapters.persistence.models import ChatSession


pytestmark = pytest.mark.db


def _chat_session(
    *,
    id: str,
    updated_at: datetime,
    created_at: datetime | None = None,
    user_id: str = "user-123",
) -> ChatSession:
    created = created_at or updated_at - timedelta(hours=1)
    return ChatSession(
        id=id,
        user_id=user_id,
        stance=None,
        summary=None,
        memory_snippets=[],
        document_ids=[],
        goals=[],
        preferences=None,
        created_at=created,
        updated_at=updated_at,
        last_interaction_at=updated_at,
    )


def test_list_recent_requires_positive_limit(session: Session) -> None:
    repo = SQLAlchemyChatSessionRepository(session)

    with pytest.raises(ValueError):
        repo.list_recent(0)

    with pytest.raises(ValueError):
        repo.list_recent(-5)


def test_list_recent_returns_sessions_in_descending_order(session: Session) -> None:
    repo = SQLAlchemyChatSessionRepository(session)
    now = datetime.now(UTC)
    sessions = [
        _chat_session(id="chat-old", updated_at=now - timedelta(days=2)),
        _chat_session(id="chat-mid", updated_at=now - timedelta(days=1)),
        _chat_session(id="chat-new", updated_at=now),
    ]
    session.add_all(sessions)
    session.flush()

    results = repo.list_recent(2)

    assert len(results) == 2
    assert results[0].id == "chat-new"
    assert results[1].id == "chat-mid"
    assert results[0].updated_at >= results[1].updated_at
