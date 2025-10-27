"""Repository for loading passage embeddings from SQLAlchemy sessions."""
from __future__ import annotations

from typing import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from theo.application.embeddings.store import PassageEmbeddingStore

from .models import PassageEmbedding


class SQLAlchemyPassageEmbeddingStore(PassageEmbeddingStore):
    """Load passage embeddings using SQLAlchemy queries."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_embedding(self, passage_id: str) -> Sequence[float] | None:
        if not passage_id:
            return None
        stmt = select(PassageEmbedding.embedding).where(
            PassageEmbedding.passage_id == passage_id
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def get_embeddings(
        self, passage_ids: Sequence[str]
    ) -> Mapping[str, Sequence[float] | None]:
        unique_ids = [identifier for identifier in dict.fromkeys(passage_ids) if identifier]
        if not unique_ids:
            return {}
        stmt = select(PassageEmbedding.passage_id, PassageEmbedding.embedding).where(
            PassageEmbedding.passage_id.in_(unique_ids)
        )
        rows = self._session.execute(stmt).all()
        result: dict[str, Sequence[float] | None] = {identifier: None for identifier in unique_ids}
        for passage_id, embedding in rows:
            result[passage_id] = embedding
        return result


__all__ = ["SQLAlchemyPassageEmbeddingStore"]
