"""SQLAlchemy-backed implementation of :class:`DocumentRepository`."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Mapping, Sequence

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from theo.application.dtos import DocumentDTO, DocumentSummaryDTO
from theo.application.observability import trace_repository_call
from theo.application.repositories.document_repository import DocumentRepository
from theo.domain.discoveries import DocumentEmbedding
from theo.application.facades.settings import get_settings
from theo.application.embeddings.store import PassageEmbeddingService

from .mappers import document_summary_to_dto, document_to_dto
from .models import Document, Passage, _PREFETCHED_EMBEDDING_ATTR
from .passage_embedding_store import SQLAlchemyPassageEmbeddingStore


class SQLAlchemyDocumentRepository(DocumentRepository):
    """Document repository using SQLAlchemy sessions."""

    def __init__(
        self,
        session: Session,
        *,
        embedding_service: PassageEmbeddingService | None = None,
    ) -> None:
        self.session = session
        if embedding_service is None:
            settings = get_settings()
            store = SQLAlchemyPassageEmbeddingStore(session)
            embedding_service = PassageEmbeddingService(
                store, cache_max_size=settings.embedding_cache_size
            )
        self._embedding_service = embedding_service

    def list_with_embeddings(self, user_id: str) -> list[DocumentEmbedding]:
        """Return documents belonging to *user_id* with averaged embeddings."""

        with trace_repository_call(
            "document",
            "list_with_embeddings",
            attributes={"user_id": user_id},
        ) as trace:
            stmt = (
                select(Document)
                .where(Document.collection == user_id)
                .options(selectinload(Document.passages))
            )
            documents = self.session.scalars(stmt).all()

            trace.set_attribute("documents_fetched", len(documents))

            all_passages = [
                passage for document in documents for passage in document.passages
            ]
            embedding_map = self._prefetch_embeddings(all_passages)

            results: list[DocumentEmbedding] = []
            for document in documents:
                vectors: list[Sequence[float]] = []
                for passage in document.passages:
                    embedding = self._resolve_embedding(passage, embedding_map)
                    if isinstance(embedding, Sequence) and len(embedding) > 0:
                        vectors.append(embedding)
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

            trace.record_result_count(len(results))
            return results

    def get_by_id(self, document_id: str) -> DocumentDTO | None:
        """Retrieve a single document by identifier."""

        with trace_repository_call(
            "document",
            "get_by_id",
            attributes={"document_id": document_id},
        ) as trace:
            stmt = (
                select(Document)
                .options(selectinload(Document.passages))
                .where(Document.id == document_id)
            )
            document = self.session.scalars(stmt).first()
            trace.set_attribute("hit", document is not None)
            if document is None:
                trace.record_result_count(0)
                return None

            self._prefetch_embeddings(document.passages)

            trace.record_result_count(1)
            return document_to_dto(document)

    def list_summaries(
        self, user_id: str, limit: int | None = None
    ) -> list[DocumentSummaryDTO]:
        """Return summaries for *user_id* limited by *limit* if provided."""

        with trace_repository_call(
            "document",
            "list_summaries",
            attributes={"user_id": user_id, "limit": limit},
        ) as trace:
            stmt = select(Document).where(Document.collection == user_id)
            if limit is not None:
                stmt = stmt.limit(limit)
            documents = self.session.scalars(stmt).all()
            trace.record_result_count(len(documents))
            return [document_summary_to_dto(doc) for doc in documents]

    def list_created_since(
        self, since: datetime, limit: int | None = None
    ) -> list[DocumentDTO]:
        """Return documents created on/after *since* ordered by timestamp."""

        with trace_repository_call(
            "document",
            "list_created_since",
            attributes={"limit": limit, "since": since.isoformat()},
        ) as trace:
            stmt = (
                select(Document)
                .options(selectinload(Document.passages))
                .where(Document.created_at >= since)
                .order_by(Document.created_at.asc())
            )
            if limit is not None:
                stmt = stmt.limit(limit)
            documents = self.session.scalars(stmt).all()
            for document in documents:
                self._prefetch_embeddings(document.passages)
            trace.record_result_count(len(documents))
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

    def _prefetch_embeddings(
        self, passages: Iterable[Passage]
    ) -> Mapping[str, Sequence[float] | None]:
        collected: list[Passage] = list(passages)
        unique_ids: list[str] = []
        seen: set[str] = set()
        for passage in collected:
            identifier = getattr(passage, "id", None)
            if isinstance(identifier, str) and identifier not in seen:
                unique_ids.append(identifier)
                seen.add(identifier)
        if not unique_ids:
            return {}
        mapping = self._embedding_service.get_many(unique_ids)
        for passage in collected:
            identifier = getattr(passage, "id", None)
            if isinstance(identifier, str):
                setattr(passage, _PREFETCHED_EMBEDDING_ATTR, mapping.get(identifier))
        return mapping

    @staticmethod
    def _resolve_embedding(
        passage: Passage, embedding_map: Mapping[str, Sequence[float] | None]
    ) -> Sequence[float] | None:
        identifier = getattr(passage, "id", None)
        if isinstance(identifier, str):
            if hasattr(passage, _PREFETCHED_EMBEDDING_ATTR):
                return getattr(passage, _PREFETCHED_EMBEDDING_ATTR)
            value = embedding_map.get(identifier)
            setattr(passage, _PREFETCHED_EMBEDDING_ATTR, value)
            return value
        return passage.embedding


__all__ = ["SQLAlchemyDocumentRepository"]

