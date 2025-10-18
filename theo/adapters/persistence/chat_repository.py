"""SQLAlchemy implementation of the chat session repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from theo.application.dtos import ChatSessionDTO
from theo.application.repositories import ChatSessionRepository

from .mappers import chat_session_to_dto
from .models import ChatSession


class SQLAlchemyChatSessionRepository(ChatSessionRepository):
    """Chat session repository backed by a SQLAlchemy session."""

    def __init__(self, session: Session):
        self.session = session

    def list_recent(self, limit: int) -> list[ChatSessionDTO]:
        stmt = (
            select(ChatSession)
            .order_by(ChatSession.updated_at.desc())
            .limit(max(1, limit))
        )
        results = self.session.scalars(stmt).all()
        return [chat_session_to_dto(model) for model in results]


__all__ = ["SQLAlchemyChatSessionRepository"]

