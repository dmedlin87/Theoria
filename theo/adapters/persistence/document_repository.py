"""SQLAlchemy-backed implementation of :class:`DocumentRepository`."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from theo.application.dtos import DocumentDTO, DocumentSummaryDTO
from theo.application.repositories.document_repository import DocumentRepository
from theo.domain.discoveries import DocumentEmbedding

from .mappers import document_summary_to_dto, document_to_dto
from .models import Document


class SQLAlchemyDocumentRepository(DocumentRepository):
    """Document repository using SQLAlchemy sessions."""

    def __init__(self, session: Session):
        self.session = session

    def list_with_embeddings(self, user_id: str) -> list[DocumentEmbedding]:
        """Return documents belonging to *user_id* with averaged embeddings."""

        stmt = (
            select(Document)
            .where(Document.collection == user_id)
            .options(selectinload(Document.passages))
        )
        documents = self.session.scalars(stmt).all()

        results: list[DocumentEmbedding] = []
        for document in documents:
            vectors = [
                passage.embedding
                for passage in document.passages
                if isinstance(passage.embedding, Sequence)
                and len(passage.embedding) > 0
            ]
            if not vectors:
                continue

            averaged = self._average_vectors(vectors)
            if not averaged:
                continue

            verse_ids = self._collect_verse_ids(document.passages)
            topics = self._extract_topics(document.topics)

            results.append(
                DocumentEmbedding(
                    document_id=document.id,
                    title=document.title or "Untitled Document",
                    abstract=document.abstract,
                    topics=topics,
                    verse_ids=verse_ids,
                    embedding=averaged,
                    metadata={"keywords": topics, "documentId": document.id},
                )
            )

        return results

    def get_by_id(self, document_id: str) -> DocumentDTO | None:
        """Retrieve a single document by identifier."""

        document = self.session.get(Document, document_id)
        if document is None:
            return None
        return document_to_dto(document)

    def list_summaries(
        self, user_id: str, limit: int | None = None
    ) -> list[DocumentSummaryDTO]:
        """Return summaries for *user_id* limited by *limit* if provided."""

        stmt = select(Document).where(Document.collection == user_id)
        if limit is not None:
            stmt = stmt.limit(limit)
        documents = self.session.scalars(stmt).all()
        return [document_summary_to_dto(doc) for doc in documents]

    def list_created_since(
        self, since: datetime, limit: int | None = None
    ) -> list[DocumentDTO]:
        """Return documents created on/after *since* ordered by timestamp."""

        stmt = (
            select(Document)
            .where(Document.created_at >= since)
            .order_by(Document.created_at.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        documents = self.session.scalars(stmt).all()
        return [document_to_dto(doc) for doc in documents]

    @staticmethod
    def _average_vectors(vectors: Sequence[Sequence[float]]) -> list[float]:
        array = np.array(vectors, dtype=float)
        if not np.isfinite(array).all():
            mask = np.isfinite(array).all(axis=1)
            array = array[mask]
        if len(array) == 0:
            return []
        return array.mean(axis=0).tolist()

    @staticmethod
    def _collect_verse_ids(passages) -> list[int]:
        verse_ids: set[int] = set()
        for passage in passages:
            raw_ids = getattr(passage, "osis_verse_ids", None)
            if isinstance(raw_ids, Iterable):
                for item in raw_ids:
                    if isinstance(item, int):
                        verse_ids.add(item)
        return sorted(verse_ids)

    @staticmethod
    def _extract_topics(raw_topics: object) -> list[str]:
        topics: list[str] = []
        if isinstance(raw_topics, str):
            value = raw_topics.strip()
            if value:
                topics.append(value)
        elif isinstance(raw_topics, Iterable):
            for item in raw_topics:
                if isinstance(item, str):
                    value = item.strip()
                    if value:
                        topics.append(value)
                elif isinstance(item, dict):
                    for key in ("label", "name", "topic", "value"):
                        candidate = item.get(key)
                        if isinstance(candidate, str):
                            value = candidate.strip()
                            if value:
                                topics.append(value)
                                break
        return topics


__all__ = ["SQLAlchemyDocumentRepository"]

