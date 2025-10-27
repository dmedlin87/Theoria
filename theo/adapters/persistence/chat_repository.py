"""SQLAlchemy implementation of the chat session repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from theo.application.dtos import ChatSessionDTO
from theo.application.observability import trace_repository_call
from theo.application.repositories import ChatSessionRepository

from .base_repository import BaseRepository
from .mappers import chat_session_to_dto
from .models import ChatSession


class SQLAlchemyChatSessionRepository(
    BaseRepository[ChatSession], ChatSessionRepository
):
    """Chat session repository backed by a SQLAlchemy session."""

    def __init__(self, session: Session):
        super().__init__(session)

    def list_recent(self, limit: int) -> list[ChatSessionDTO]:
        if limit < 1:
            raise ValueError("limit must be a positive integer")

        with trace_repository_call(
            "chat_session",
            "list_recent",
            attributes={"limit": limit},
        ) as trace:
            stmt = (
                select(ChatSession)
                .order_by(ChatSession.updated_at.desc())
                .limit(limit)
            )
            results = self.scalars(stmt).all()
            trace.record_result_count(len(results))
            return [chat_session_to_dto(model) for model in results]


__all__ = ["SQLAlchemyChatSessionRepository"]

