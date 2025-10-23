"""Mappers convert between ORM models and application DTOs.

These functions handle the translation between database representation
and application-layer objects, keeping the adapter layer separate from
business logic.
"""

from __future__ import annotations

from typing import Sequence

from theo.application.dtos import (
    ChatSessionDTO,
    CorpusSnapshotDTO,
    DiscoveryDTO,
    DocumentDTO,
    DocumentSummaryDTO,
    PassageDTO,
)

from .models import (
    ChatSession,
    CorpusSnapshot,
    Discovery,
    Document,
    Passage,
)


def chat_session_to_dto(model: ChatSession) -> ChatSessionDTO:
    """Convert ORM ChatSession to DTO."""

    return ChatSessionDTO(
        id=model.id,
        user_id=model.user_id,
        memory_snippets=list(model.memory_snippets or []),
        updated_at=model.updated_at,
    )


def discovery_to_dto(model: Discovery) -> DiscoveryDTO:
    """Convert ORM Discovery to application DTO."""
    return DiscoveryDTO(
        id=model.id,
        user_id=model.user_id,
        discovery_type=model.discovery_type,
        title=model.title,
        description=model.description,
        confidence=model.confidence,
        relevance_score=model.relevance_score,
        viewed=model.viewed,
        user_reaction=model.user_reaction,
        created_at=model.created_at,
        metadata=model.meta or {},
    )


def dto_to_discovery(dto: DiscoveryDTO) -> Discovery:
    """Convert application DTO to ORM Discovery.

    Note: Does not set id, as it's typically auto-generated.
    """
    return Discovery(
        user_id=dto.user_id,
        discovery_type=dto.discovery_type,
        title=dto.title,
        description=dto.description,
        confidence=dto.confidence,
        relevance_score=dto.relevance_score,
        viewed=dto.viewed,
        user_reaction=dto.user_reaction,
        created_at=dto.created_at,
        meta=dict(dto.metadata) if dto.metadata else None,
    )


def corpus_snapshot_to_dto(model: CorpusSnapshot) -> CorpusSnapshotDTO:
    """Convert ORM CorpusSnapshot to application DTO."""
    return CorpusSnapshotDTO(
        id=model.id,
        user_id=model.user_id,
        snapshot_date=model.snapshot_date,
        document_count=model.document_count,
        verse_coverage=model.verse_coverage or {},
        dominant_themes=model.dominant_themes or {},
        metadata=model.meta or {},
    )


def document_summary_to_dto(model: Document) -> DocumentSummaryDTO:
    """Convert ORM Document to lightweight summary DTO."""
    topics: list[str] = []
    if isinstance(model.topics, list):
        topics = [str(t) for t in model.topics if isinstance(t, str)]

    return DocumentSummaryDTO(
        id=model.id,
        title=model.title,
        authors=model.authors,
        collection=model.collection,
        source_type=model.source_type,
        topics=topics,
        created_at=model.created_at,
    )


def passage_to_dto(model: Passage) -> PassageDTO:
    """Convert ORM Passage to application DTO."""
    return PassageDTO(
        id=model.id,
        document_id=model.document_id,
        text=model.text,
        page_no=model.page_no,
        start_char=model.start_char,
        end_char=model.end_char,
        osis_ref=model.osis_ref,
        osis_verse_ids=model.osis_verse_ids,
        embedding=model.embedding,
    )


def document_to_dto(model: Document, passages: Sequence[Passage] | None = None) -> DocumentDTO:
    """Convert ORM Document with passages to complete DTO."""
    topics: list[str] = []
    if isinstance(model.topics, list):
        topics = [str(t) for t in model.topics if isinstance(t, str)]

    passage_dtos = []
    if passages is not None:
        passage_dtos = [passage_to_dto(p) for p in passages]
    elif hasattr(model, 'passages') and model.passages:
        passage_dtos = [passage_to_dto(p) for p in model.passages]

    return DocumentDTO(
        id=model.id,
        title=model.title,
        authors=model.authors,
        collection=model.collection,
        source_type=model.source_type,
        abstract=model.abstract,
        topics=topics,
        venue=model.venue,
        year=model.year,
        created_at=model.created_at,
        updated_at=model.updated_at,
        passages=passage_dtos,
    )


__all__ = [
    "chat_session_to_dto",
    "discovery_to_dto",
    "dto_to_discovery",
    "corpus_snapshot_to_dto",
    "document_summary_to_dto",
    "document_to_dto",
    "passage_to_dto",
]
