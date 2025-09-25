"""Database models for Theo Engine."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from ..core.settings import get_settings
from .types import TSVectorType, VectorType


class Document(Base):
    """Source artifact ingested into the system."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    authors: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    doi: Mapped[str | None] = mapped_column(String, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String, nullable=True)
    collection: Mapped[str | None] = mapped_column(String, nullable=True)
    pub_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    venue: Mapped[str | None] = mapped_column(String, nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    topics: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    channel: Mapped[str | None] = mapped_column(String, nullable=True)
    video_id: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bib_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String, unique=True)
    storage_path: Mapped[str | None] = mapped_column(String, nullable=True)
    enrichment_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provenance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    passages: Mapped[list["Passage"]] = relationship(
        "Passage", back_populates="document", cascade="all, delete-orphan"
    )
    annotations: Mapped[list["DocumentAnnotation"]] = relationship(
        "DocumentAnnotation", back_populates="document", cascade="all, delete-orphan"
    )


class Passage(Base):
    """Chunked content extracted from a document."""

    __tablename__ = "passages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id", ondelete="CASCADE"))
    page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    t_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    t_end: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    osis_ref: Mapped[str | None] = mapped_column(String, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        VectorType(get_settings().embedding_dim), nullable=True
    )
    lexeme: Mapped[str | None] = mapped_column(TSVectorType(), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    document: Mapped[Document] = relationship("Document", back_populates="passages")


class AppSetting(Base):
    """Simple key/value store for application-level configuration."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class DocumentAnnotation(Base):
    """Free-form annotations associated with a document."""

    __tablename__ = "document_annotations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    document: Mapped[Document] = relationship("Document", back_populates="annotations")


class IngestionJob(Base):
    """Track asynchronous ingestion and enrichment work."""

    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str | None] = mapped_column(String, ForeignKey("documents.id"), nullable=True)
    job_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    task_id: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    document: Mapped[Document | None] = relationship("Document")


class ResearchNote(Base):
    """Structured study note anchored to an OSIS reference."""

    __tablename__ = "research_notes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    osis: Mapped[str] = mapped_column(String, index=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    stance: Mapped[str | None] = mapped_column(String, nullable=True)
    claim_type: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    evidences: Mapped[list["NoteEvidence"]] = relationship(
        "NoteEvidence", back_populates="note", cascade="all, delete-orphan"
    )


class NoteEvidence(Base):
    """Citation or supporting reference attached to a research note."""

    __tablename__ = "note_evidence"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    note_id: Mapped[str] = mapped_column(
        String, ForeignKey("research_notes.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str | None] = mapped_column(String, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    osis_refs: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    citation: Mapped[str | None] = mapped_column(String, nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    note: Mapped[ResearchNote] = relationship("ResearchNote", back_populates="evidences")


class CrossReference(Base):
    """Graph edge linking two OSIS references together."""

    __tablename__ = "cross_references"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    source_osis: Mapped[str] = mapped_column(String, index=True, nullable=False)
    target_osis: Mapped[str] = mapped_column(String, index=True, nullable=False)
    relation_type: Mapped[str | None] = mapped_column(String, nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    dataset: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


__all__ = [
    "Document",
    "Passage",
    "AppSetting",
    "DocumentAnnotation",
    "IngestionJob",
    "ResearchNote",
    "NoteEvidence",
    "CrossReference",
]
