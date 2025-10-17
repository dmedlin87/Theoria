"""GraphQL type definitions mapping domain objects to the schema."""

from __future__ import annotations

from datetime import datetime
import strawberry

from theo.domain import Document, DocumentId, DocumentMetadata
from theo.domain.research.overview import OverviewBullet
from theo.domain.research.scripture import Verse as DomainVerse


@strawberry.type
class DocumentMetadataType:
    """Metadata describing a theological document."""

    title: str
    source: str
    language: str | None = None
    created_at: datetime | None = strawberry.field(default=None, name="createdAt")
    updated_at: datetime | None = strawberry.field(default=None, name="updatedAt")

    @staticmethod
    def from_domain(metadata: DocumentMetadata) -> "DocumentMetadataType":
        return DocumentMetadataType(
            title=metadata.title,
            source=metadata.source,
            language=metadata.language,
            created_at=metadata.created_at,
            updated_at=metadata.updated_at,
        )


@strawberry.type
class DocumentType:
    """GraphQL representation of the document aggregate."""

    id: strawberry.ID
    metadata: DocumentMetadataType
    scripture_refs: list[str] = strawberry.field(name="scriptureRefs")
    tags: list[str]
    checksum: str | None = None

    @staticmethod
    def from_domain(document: Document) -> "DocumentType":
        return DocumentType(
            id=str(document.id),
            metadata=DocumentMetadataType.from_domain(document.metadata),
            scripture_refs=list(document.scripture_refs),
            tags=list(document.tags),
            checksum=document.checksum,
        )


@strawberry.input
class DocumentMetadataInput:
    """Input metadata required to ingest a document."""

    title: str
    source: str
    language: str | None = None

    def to_domain(self) -> DocumentMetadata:
        return DocumentMetadata(
            title=self.title,
            source=self.source,
            language=self.language,
        )


@strawberry.input
class DocumentInput:
    """Input payload describing a document to ingest."""

    id: strawberry.ID
    metadata: DocumentMetadataInput
    scripture_refs: list[str] = strawberry.field(default_factory=list, name="scriptureRefs")
    tags: list[str] = strawberry.field(default_factory=list)
    checksum: str | None = None

    def to_domain(self) -> Document:
        return Document(
            id=DocumentId(str(self.id)),
            metadata=self.metadata.to_domain(),
            scripture_refs=tuple(self.scripture_refs),
            tags=tuple(self.tags),
            checksum=self.checksum,
        )


@strawberry.type
class VerseType:
    """Scripture verse fetched from research datasets."""

    osis: str
    translation: str
    text: str
    book: str | None = None
    chapter: int | None = None
    verse: int | None = None

    @staticmethod
    def from_domain(verse: DomainVerse) -> "VerseType":
        return VerseType(
            osis=verse.osis,
            translation=verse.translation,
            text=verse.text,
            book=verse.book,
            chapter=verse.chapter,
            verse=verse.verse,
        )


@strawberry.type
class InsightType:
    """An insight derived from reliability overview analysis."""

    category: str
    summary: str
    citations: list[str]

    @staticmethod
    def from_overview(category: str, bullet: OverviewBullet) -> "InsightType":
        return InsightType(
            category=category,
            summary=bullet.summary,
            citations=list(bullet.citations),
        )


@strawberry.type
class IngestDocumentPayload:
    """Response payload returned by the ``ingestDocument`` mutation."""

    document_id: strawberry.ID = strawberry.field(name="documentId")

    @staticmethod
    def from_document_id(document_id: DocumentId) -> "IngestDocumentPayload":
        return IngestDocumentPayload(document_id=str(document_id))


__all__ = [
    "DocumentInput",
    "DocumentMetadataInput",
    "DocumentMetadataType",
    "DocumentType",
    "InsightType",
    "IngestDocumentPayload",
    "VerseType",
]
