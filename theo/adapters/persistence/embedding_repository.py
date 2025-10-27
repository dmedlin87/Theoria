"""SQLAlchemy-backed repository supporting embedding rebuild workflows."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from theo.application.repositories.embedding_repository import (
    EmbeddingUpdate,
    PassageEmbeddingRepository,
    PassageForEmbedding,
)

from .models import Document, Passage, PassageEmbedding


class SQLAlchemyPassageEmbeddingRepository(PassageEmbeddingRepository):
    """Repository coordinating passage reads and embedding updates."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def count_candidates(
        self,
        *,
        fast: bool,
        changed_since: datetime | None,
        ids: Sequence[str] | None,
    ) -> int:
        stmt = select(func.count(Passage.id)).select_from(Passage)
        filters, join_document = self._build_filters(
            fast=fast, changed_since=changed_since, ids=ids
        )
        if join_document:
            stmt = stmt.join(Document)
        for criterion in filters:
            stmt = stmt.where(criterion)
        return int(self._session.execute(stmt).scalar_one())

    def existing_ids(self, ids: Sequence[str]) -> set[str]:
        if not ids:
            return set()
        stmt = select(Passage.id).where(Passage.id.in_(ids))
        return set(self._session.execute(stmt).scalars())

    def iter_candidates(
        self,
        *,
        fast: bool,
        changed_since: datetime | None,
        ids: Sequence[str] | None,
        batch_size: int,
    ) -> Iterable[PassageForEmbedding]:
        stmt = (
            select(Passage, PassageEmbedding.embedding)
            .outerjoin(PassageEmbedding)
            .order_by(Passage.id)
            .execution_options(stream_results=True, yield_per=max(1, batch_size))
        )
        filters, join_document = self._build_filters(
            fast=fast, changed_since=changed_since, ids=ids
        )
        if join_document:
            stmt = stmt.join(Document)
            stmt = stmt.add_columns(Document.updated_at)
        for criterion in filters:
            stmt = stmt.where(criterion)

        stream = self._session.execute(stmt)
        for row in stream:
            passage = row[0]
            embedding = row[1]
            document_updated_at = row[2] if join_document else None
            yield PassageForEmbedding(
                id=passage.id,
                text=passage.text,
                embedding=embedding,
                document_updated_at=document_updated_at,
            )

    def update_embeddings(self, updates: Sequence[EmbeddingUpdate]) -> None:
        if not updates:
            return
        ids = [update.id for update in updates]
        if ids:
            self._session.execute(
                delete(PassageEmbedding).where(PassageEmbedding.passage_id.in_(ids))
            )
        payload = [
            {"passage_id": update.id, "embedding": list(update.embedding)}
            for update in updates
        ]
        if payload:
            self._session.bulk_insert_mappings(PassageEmbedding, payload)

    def _build_filters(
        self,
        *,
        fast: bool,
        changed_since: datetime | None,
        ids: Sequence[str] | None,
    ) -> tuple[list, bool]:
        filters: list = []
        join_document = False
        if fast:
            filters.append(
                ~select(PassageEmbedding.passage_id)
                .where(PassageEmbedding.passage_id == Passage.id)
                .exists()
            )
        if changed_since is not None:
            join_document = True
            filters.append(Document.updated_at >= changed_since)
        if ids:
            filters.append(Passage.id.in_(ids))
        return filters, join_document


__all__ = ["SQLAlchemyPassageEmbeddingRepository"]
