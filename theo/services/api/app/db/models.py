"""Database models for Theo Engine."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.settings import get_settings
from .types import TSVectorType, VectorType


if TYPE_CHECKING:
    class DeclarativeBase:
        """Typed façade for SQLAlchemy's declarative base."""

        metadata: Any
        registry: Any

else:  # pragma: no cover - executed only at runtime
    from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base class shared by all ORM models."""

    pass


class Document(Base):
    """Source artifact ingested into the system."""

    __tablename__ = "documents"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
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
    theological_tradition: Mapped[str | None] = mapped_column(String, nullable=True)
    topic_domains: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String, unique=True)
    storage_path: Mapped[str | None] = mapped_column(String, nullable=True)
    enrichment_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provenance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
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
    video: Mapped["Video | None"] = relationship(
        "Video",
        back_populates="document",
        cascade="all, delete-orphan",
        uselist=False,
        single_parent=True,
    )
    case_objects: Mapped[list["CaseObject"]] = relationship(
        "CaseObject",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class NotebookCollaboratorRole(str, Enum):
    """Roles controlling notebook access levels."""

    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class Notebook(Base):
    """Team notebooks used for collaborative research."""

    __tablename__ = "notebooks"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String, nullable=False, index=True)
    team_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    entries: Mapped[list["NotebookEntry"]] = relationship(
        "NotebookEntry",
        back_populates="notebook",
        cascade="all, delete-orphan",
        order_by="NotebookEntry.created_at",
    )
    collaborators: Mapped[list["NotebookCollaborator"]] = relationship(
        "NotebookCollaborator",
        back_populates="notebook",
        cascade="all, delete-orphan",
    )


class NotebookEntry(Base):
    """Notebook entry tied to a source document and optional verse reference."""

    __tablename__ = "notebook_entries"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    notebook_id: Mapped[str] = mapped_column(
        String, ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    osis_ref: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    notebook: Mapped[Notebook] = relationship("Notebook", back_populates="entries")
    document: Mapped[Document | None] = relationship("Document")
    mentions: Mapped[list["EntryMention"]] = relationship(
        "EntryMention",
        back_populates="entry",
        cascade="all, delete-orphan",
    )


class EntryMention(Base):
    """Explicit verse mentions associated with a notebook entry."""

    __tablename__ = "entry_mentions"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    entry_id: Mapped[str] = mapped_column(
        String, ForeignKey("notebook_entries.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    osis_ref: Mapped[str] = mapped_column(String, nullable=False, index=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    entry: Mapped[NotebookEntry] = relationship("NotebookEntry", back_populates="mentions")
    document: Mapped[Document | None] = relationship("Document")


class NotebookCollaborator(Base):
    """Explicit collaborator access assignments for a notebook."""

    __tablename__ = "notebook_collaborators"
    __table_args__ = (
        UniqueConstraint(
            "notebook_id",
            "subject",
            name="uq_notebook_collaborators_subject",
        ),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    notebook_id: Mapped[str] = mapped_column(
        String, ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String, nullable=False, index=True)
    role: Mapped[NotebookCollaboratorRole] = mapped_column(
        SQLEnum(NotebookCollaboratorRole),
        default=NotebookCollaboratorRole.VIEWER,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    notebook: Mapped[Notebook] = relationship("Notebook", back_populates="collaborators")


class Passage(Base):
    """Chunked content extracted from a document."""

    __tablename__ = "passages"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    document_id: Mapped[str] = mapped_column(
        String, ForeignKey("documents.id", ondelete="CASCADE")
    )
    page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    t_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    t_end: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    osis_ref: Mapped[str | None] = mapped_column(String, index=True)
    osis_start_verse_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    osis_end_verse_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        VectorType(get_settings().embedding_dim), nullable=True
    )
    lexeme: Mapped[str | None] = mapped_column(TSVectorType(), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tei_xml: Mapped[str | None] = mapped_column(Text, nullable=True)

    document: Mapped[Document] = relationship("Document", back_populates="passages")
    case_object: Mapped["CaseObject | None"] = relationship(
        "CaseObject",
        back_populates="passage",
        cascade="all, delete-orphan",
        uselist=False,
    )


class AppSetting(Base):
    """Simple key/value store for application-level configuration."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSON, nullable=True
    )
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

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    document_id: Mapped[str] = mapped_column(
        String, ForeignKey("documents.id", ondelete="CASCADE")
    )
    case_object_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("case_objects.id", ondelete="SET NULL"), nullable=True
    )
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
    case_object: Mapped["CaseObject | None"] = relationship(
        "CaseObject",
        uselist=False,
        primaryjoin="DocumentAnnotation.case_object_id == CaseObject.id",
        foreign_keys="DocumentAnnotation.case_object_id",
    )


class IngestionJob(Base):
    """Track asynchronous ingestion and enrichment work."""

    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        Index(
            "uq_ingestion_jobs_job_type_args_hash",
            "job_type",
            "args_hash",
            unique=True,
            postgresql_where=text("args_hash IS NOT NULL"),
            sqlite_where=text("args_hash IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    document_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("documents.id"), nullable=True
    )
    job_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    task_id: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    args_hash: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    document: Mapped["Document | None"] = relationship("Document")


class FeedbackEventAction(str, Enum):
    """Permissible action types for user feedback events."""

    VIEW = "view"
    CLICK = "click"
    COPY = "copy"
    LIKE = "like"
    DISLIKE = "dislike"
    USED_IN_ANSWER = "used_in_answer"


class FeedbackEvent(Base):
    """Captures explicit or implicit user feedback interactions."""

    __tablename__ = "feedback_events"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    chat_session_id: Mapped[str | None] = mapped_column(
        String, index=True, nullable=True
    )
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("documents.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    passage_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("passages.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    action: Mapped[FeedbackEventAction] = mapped_column(
        SQLEnum(
            FeedbackEventAction,
            name="feedback_event_action",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
    )
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    document: Mapped["Document | None"] = relationship("Document")
    passage: Mapped["Passage | None"] = relationship("Passage")


class ResearchNote(Base):
    """Structured study note anchored to an OSIS reference."""

    __tablename__ = "research_notes"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    osis: Mapped[str] = mapped_column(String, index=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    stance: Mapped[str | None] = mapped_column(String, nullable=True)
    claim_type: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    tenant_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
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

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
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

    note: Mapped[ResearchNote] = relationship(
        "ResearchNote", back_populates="evidences"
    )


class EvidenceCard(Base):
    """Evidence card records authored via MCP."""

    __tablename__ = "evidence_cards"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    osis: Mapped[str] = mapped_column(String, nullable=False, index=True)
    claim_summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    tenant_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class Creator(Base):
    """Profile describing a recurring media creator or speaker."""

    __tablename__ = "creators"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    channel: Mapped[str | None] = mapped_column(String, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    videos: Mapped[list["Video"]] = relationship(
        "Video", back_populates="creator", cascade="all, delete-orphan"
    )
    claims: Mapped[list["CreatorClaim"]] = relationship(
        "CreatorClaim", back_populates="creator", cascade="all, delete-orphan"
    )


class Video(Base):
    """Video or media asset linked to an ingested transcript."""

    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    creator_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("creators.id", ondelete="SET NULL"), nullable=True
    )
    document_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    video_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    license: Mapped[str | None] = mapped_column(String, nullable=True)
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

    creator: Mapped[Creator | None] = relationship("Creator", back_populates="videos")
    document: Mapped[Document | None] = relationship("Document", back_populates="video")
    segments: Mapped[list["TranscriptSegment"]] = relationship(
        "TranscriptSegment", back_populates="video", cascade="all, delete-orphan"
    )
    claims: Mapped[list["CreatorClaim"]] = relationship(
        "CreatorClaim", back_populates="video", cascade="all, delete-orphan"
    )
    quotes: Mapped[list["TranscriptQuote"]] = relationship(
        "TranscriptQuote", back_populates="video", cascade="all, delete-orphan"
    )


class TranscriptSegment(Base):
    """Time-coded transcript span enriched with metadata."""

    __tablename__ = "transcript_segments"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    document_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    video_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("videos.id", ondelete="CASCADE"), nullable=True
    )
    t_start: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    t_end: Mapped[float | None] = mapped_column(Float, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_osis: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    osis_refs: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    topics: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    entities: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    video: Mapped[Video | None] = relationship("Video", back_populates="segments")
    document: Mapped[Document | None] = relationship("Document")
    quotes: Mapped[list["TranscriptQuote"]] = relationship(
        "TranscriptQuote", back_populates="segment", cascade="all, delete-orphan"
    )
    claims: Mapped[list["CreatorClaim"]] = relationship(
        "CreatorClaim", back_populates="segment", cascade="all, delete-orphan"
    )


class CreatorClaim(Base):
    """Structured stance or claim derived from creator transcripts."""

    __tablename__ = "creator_claims"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    creator_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("creators.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    video_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("videos.id", ondelete="SET NULL"), nullable=True
    )
    segment_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("transcript_segments.id", ondelete="SET NULL"), nullable=True
    )
    topic: Mapped[str] = mapped_column(String, nullable=False, index=True)
    stance: Mapped[str | None] = mapped_column(String, nullable=True)
    claim_md: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    creator: Mapped[Creator | None] = relationship("Creator", back_populates="claims")
    video: Mapped[Video | None] = relationship("Video", back_populates="claims")
    segment: Mapped[TranscriptSegment | None] = relationship(
        "TranscriptSegment", back_populates="claims"
    )


class TranscriptQuote(Base):
    """Highlighted quote from a transcript segment with citation metadata."""

    __tablename__ = "transcript_quotes"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    video_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("videos.id", ondelete="SET NULL"), nullable=True
    )
    segment_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("transcript_segments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    quote_md: Mapped[str] = mapped_column(Text, nullable=False)
    osis_refs: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    salience: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    video: Mapped[Video | None] = relationship("Video", back_populates="quotes")
    segment: Mapped[TranscriptSegment | None] = relationship(
        "TranscriptSegment", back_populates="quotes"
    )


class CreatorVerseRollup(Base):
    """Cached aggregation of creator perspectives for a verse or short range."""

    __tablename__ = "creator_verse_rollups"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    osis: Mapped[str] = mapped_column(String, nullable=False, index=True)
    creator_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("creators.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stance_counts: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    avg_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    claim_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    top_quote_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    creator: Mapped[Creator] = relationship("Creator")


class CrossReference(Base):
    """Graph edge linking two OSIS references together."""

    __tablename__ = "cross_references"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
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


class ContradictionSeed(Base):
    """Pre-seeded claims of harmony or tension between passages."""

    __tablename__ = "contradiction_seeds"
    __table_args__ = (
        Index("ix_contradiction_seeds_osis_a", "osis_a"),
        Index("ix_contradiction_seeds_osis_b", "osis_b"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    osis_a: Mapped[str] = mapped_column(String, nullable=False)
    osis_b: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    perspective: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class HarmonySeed(Base):
    """Pre-seeded harmony notes aligning overlapping passages."""

    __tablename__ = "harmony_seeds"
    __table_args__ = (
        Index("ix_harmony_seeds_osis_a", "osis_a"),
        Index("ix_harmony_seeds_osis_b", "osis_b"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    osis_a: Mapped[str] = mapped_column(String, nullable=False)
    osis_b: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    perspective: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class CommentaryExcerptSeed(Base):
    """Curated commentary excerpts anchored to an OSIS reference."""

    __tablename__ = "commentary_excerpt_seeds"
    __table_args__ = (Index("ix_commentary_excerpt_seeds_osis", "osis"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    osis: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    perspective: Mapped[str | None] = mapped_column(String, nullable=True)
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


class AgentTrail(Base):
    """Persisted record of an automated agent workflow."""

    __tablename__ = "agent_trails"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    workflow: Mapped[str] = mapped_column(String, nullable=False)
    mode: Mapped[str | None] = mapped_column(String, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    plan_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_payload: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    output_payload: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_replayed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    steps: Mapped[list["AgentStep"]] = relationship(
        "AgentStep",
        back_populates="trail",
        cascade="all, delete-orphan",
        order_by="AgentStep.step_index",
    )
    sources: Mapped[list["TrailSource"]] = relationship(
        "TrailSource", back_populates="trail", cascade="all, delete-orphan"
    )
    retrieval_snapshots: Mapped[list["TrailRetrievalSnapshot"]] = relationship(
        "TrailRetrievalSnapshot",
        back_populates="trail",
        cascade="all, delete-orphan",
        order_by="TrailRetrievalSnapshot.turn_index",
    )


class ChatSession(Base):
    """Persisted conversational memory for chat workflows."""

    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    stance: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    memory_snippets: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    document_ids: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    preferences: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_interaction_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class AgentStep(Base):
    """Ordered step executed during a trail run."""

    __tablename__ = "agent_steps"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    trail_id: Mapped[str] = mapped_column(
        String, ForeignKey("agent_trails.id", ondelete="CASCADE")
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    tool: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="completed")
    input_payload: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    output_payload: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    output_digest: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    trail: Mapped[AgentTrail] = relationship("AgentTrail", back_populates="steps")
    retrieval_snapshot: Mapped["TrailRetrievalSnapshot | None"] = relationship(
        "TrailRetrievalSnapshot",
        back_populates="step",
        uselist=False,
    )


class TrailSource(Base):
    """Source reference used during a trail run."""

    __tablename__ = "trail_sources"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    trail_id: Mapped[str] = mapped_column(
        String, ForeignKey("agent_trails.id", ondelete="CASCADE")
    )
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    reference: Mapped[str] = mapped_column(String, nullable=False)
    meta: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    trail: Mapped[AgentTrail] = relationship("AgentTrail", back_populates="sources")


class TrailRetrievalSnapshot(Base):
    """Snapshot of passages and identifiers used to ground a turn."""

    __tablename__ = "trail_retrieval_snapshots"
    __table_args__ = (
        UniqueConstraint("trail_id", "turn_index", name="uq_trail_retrieval_turn"),
        Index("ix_trail_retrieval_trail", "trail_id"),
        Index("ix_trail_retrieval_hash", "retrieval_hash"),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    trail_id: Mapped[str] = mapped_column(
        String, ForeignKey("agent_trails.id", ondelete="CASCADE")
    )
    step_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("agent_steps.id", ondelete="SET NULL"), nullable=True
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    retrieval_hash: Mapped[str] = mapped_column(String, nullable=False)
    passage_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    osis_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    trail: Mapped[AgentTrail] = relationship(
        "AgentTrail", back_populates="retrieval_snapshots"
    )
    step: Mapped[AgentStep | None] = relationship(
        "AgentStep", back_populates="retrieval_snapshot"
    )


class UserWatchlist(Base):
    """Persisted definition of a personalised alert watchlist."""

    __tablename__ = "user_watchlists"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    filters: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    cadence: Mapped[str] = mapped_column(String, nullable=False, default="daily")
    delivery_channels: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    events: Mapped[list["WatchlistEvent"]] = relationship(
        "WatchlistEvent", back_populates="watchlist", cascade="all, delete-orphan"
    )


class WatchlistEvent(Base):
    """Execution record of a watchlist evaluation run."""

    __tablename__ = "watchlist_events"
    __table_args__ = (
        Index(
            "ix_watchlist_events_watchlist_id_run_started",
            "watchlist_id",
            "run_started",
        ),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    watchlist_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("user_watchlists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_started: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    run_completed: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    matches: Mapped[list[dict] | dict | None] = mapped_column(JSON, nullable=True)
    document_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    passage_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    delivery_status: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    watchlist: Mapped[UserWatchlist] = relationship(
        "UserWatchlist", back_populates="events"
    )


class GeoAncientPlace(Base):
    """Canonical OpenBible place keyed by ancient identifier."""

    __tablename__ = "geo_place"

    ancient_id: Mapped[str] = mapped_column(String, primary_key=True)
    friendly_id: Mapped[str] = mapped_column(String, nullable=False)
    classification: Mapped[str | None] = mapped_column(String, nullable=True)
    raw: Mapped[dict] = mapped_column(JSON, nullable=False)

    verses: Mapped[list["GeoPlaceVerse"]] = relationship(
        "GeoPlaceVerse", back_populates="place", cascade="all, delete-orphan"
    )


class GeoModernLocation(Base):
    """Modern geographic expression linked to ancient places."""

    __tablename__ = "geo_location"

    modern_id: Mapped[str] = mapped_column(String, primary_key=True)
    friendly_id: Mapped[str] = mapped_column(String, nullable=False)
    geom_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    names: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw: Mapped[dict] = mapped_column(JSON, nullable=False)


class GeoPlaceVerse(Base):
    """Join table linking ancient places to OSIS references."""

    __tablename__ = "geo_place_verse"
    __table_args__ = (Index("idx_geo_place_verse_osis", "osis_ref"),)

    ancient_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("geo_place.ancient_id", ondelete="CASCADE"),
        primary_key=True,
    )
    osis_ref: Mapped[str] = mapped_column(String, primary_key=True)

    place: Mapped[GeoAncientPlace] = relationship("GeoAncientPlace", back_populates="verses")


class GeoGeometry(Base):
    """Complex geometry payloads for large features."""

    __tablename__ = "geo_geometry"

    geometry_id: Mapped[str] = mapped_column(String, primary_key=True)
    geom_type: Mapped[str | None] = mapped_column(String, nullable=True)
    geojson: Mapped[dict] = mapped_column(JSON, nullable=False)


class GeoImage(Base):
    """Image metadata keyed by owner and thumbnail asset."""

    __tablename__ = "geo_image"

    image_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_kind: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, primary_key=True)
    thumb_file: Mapped[str] = mapped_column(String, primary_key=True)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    license: Mapped[str | None] = mapped_column(String, nullable=True)
    attribution: Mapped[str | None] = mapped_column(String, nullable=True)


class GeoPlace(Base):
    """Normalized lookup table for biblical geography."""

    __tablename__ = "geo_places"

    slug: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    aliases: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    sources: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class CaseObjectType(str, Enum):
    """Enumeration of object kinds mirrored into the Case Builder."""

    PASSAGE = "passage"
    NOTE = "note"
    CLAIM = "claim"
    EVIDENCE = "evidence"
    ANNOTATION = "annotation"


class CaseEdgeKind(str, Enum):
    """Types of relationships between Case Builder objects."""

    SEMANTIC_SIM = "semantic_sim"
    CO_CITATION = "co_citation"
    VERSE_OVERLAP = "verse_overlap"
    TOPIC_OVERLAP = "topic_overlap"
    CONTRADICTION = "contradiction"


class CaseInsightType(str, Enum):
    """Insight categories emitted by the Case Builder."""

    CONVERGENCE = "convergence"
    COLLISION = "collision"
    LEAD = "lead"
    BUNDLE = "bundle"


class CaseUserActionType(str, Enum):
    """Actions an analyst can take on a Case Builder insight."""

    ACCEPT = "accept"
    SNOOZE = "snooze"
    DISCARD = "discard"
    PIN = "pin"
    MUTE = "mute"


class CaseSource(Base):
    """Source metadata powering case-builder evidence objects."""

    __tablename__ = "case_sources"
    __table_args__ = (Index("ix_case_sources_document_id", "document_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("documents.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    origin: Mapped[str | None] = mapped_column(String, nullable=True)
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    modality: Mapped[str | None] = mapped_column(String, nullable=True)
    meta: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
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
    objects: Mapped[list["CaseObject"]] = relationship(
        "CaseObject",
        back_populates="source",
    )


class CaseObject(Base):
    """Evidence object evaluated by the Case Builder pipeline."""

    __tablename__ = "case_objects"
    __table_args__ = (
        Index("ix_case_objects_source_id", "source_id"),
        Index("ix_case_objects_document_id", "document_id"),
        Index("ix_case_objects_created_at", "created_at"),
        UniqueConstraint("passage_id", name="uq_case_objects_passage_id"),
        UniqueConstraint("annotation_id", name="uq_case_objects_annotation_id"),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    source_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("case_sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    document_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
    )
    passage_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("passages.id", ondelete="CASCADE"),
        nullable=True,
    )
    annotation_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("document_annotations.id", ondelete="SET NULL"),
        nullable=True,
    )
    object_type: Mapped[CaseObjectType] = mapped_column(
        SQLEnum(CaseObjectType, name="case_object_type"),
        nullable=False,
        default=CaseObjectType.PASSAGE,
    )
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    osis_ranges: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    modality: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        VectorType(get_settings().embedding_dim), nullable=True
    )
    stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    source: Mapped[CaseSource | None] = relationship("CaseSource", back_populates="objects")
    document: Mapped[Document | None] = relationship("Document", back_populates="case_objects")
    passage: Mapped[Passage | None] = relationship("Passage", back_populates="case_object")
    annotation: Mapped[DocumentAnnotation | None] = relationship(
        "DocumentAnnotation",
        uselist=False,
        primaryjoin="CaseObject.annotation_id == DocumentAnnotation.id",
        foreign_keys="CaseObject.annotation_id",
    )
    outgoing_edges: Mapped[list["CaseEdge"]] = relationship(
        "CaseEdge",
        back_populates="src_object",
        cascade="all, delete-orphan",
        foreign_keys="CaseEdge.src_object_id",
    )
    incoming_edges: Mapped[list["CaseEdge"]] = relationship(
        "CaseEdge",
        back_populates="dst_object",
        cascade="all, delete-orphan",
        foreign_keys="CaseEdge.dst_object_id",
    )
    insights: Mapped[list["CaseInsight"]] = relationship(
        "CaseInsight",
        back_populates="primary_object",
    )


class CaseEdge(Base):
    """Property-graph edge captured between Case Builder objects."""

    __tablename__ = "case_edges"
    __table_args__ = (
        Index("ix_case_edges_src", "src_object_id"),
        Index("ix_case_edges_dst", "dst_object_id"),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    src_object_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("case_objects.id", ondelete="CASCADE"),
        nullable=False,
    )
    dst_object_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("case_objects.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[CaseEdgeKind] = mapped_column(
        SQLEnum(CaseEdgeKind, name="case_edge_kind"), nullable=False
    )
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    features: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    src_object: Mapped[CaseObject] = relationship(
        "CaseObject",
        foreign_keys=[src_object_id],
        back_populates="outgoing_edges",
    )
    dst_object: Mapped[CaseObject] = relationship(
        "CaseObject",
        foreign_keys=[dst_object_id],
        back_populates="incoming_edges",
    )


class CaseInsight(Base):
    """Insight record emitted by the Case Builder pipeline."""

    __tablename__ = "case_insights"
    __table_args__ = (
        Index("ix_case_insights_type", "insight_type"),
        Index("ix_case_insights_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    primary_object_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("case_objects.id", ondelete="SET NULL"),
        nullable=True,
    )
    insight_type: Mapped[CaseInsightType] = mapped_column(
        SQLEnum(CaseInsightType, name="case_insight_type"),
        nullable=False,
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    cluster_id: Mapped[str | None] = mapped_column(String, nullable=True)
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

    primary_object: Mapped[CaseObject | None] = relationship(
        "CaseObject", back_populates="insights"
    )
    user_actions: Mapped[list["CaseUserAction"]] = relationship(
        "CaseUserAction",
        back_populates="insight",
        cascade="all, delete-orphan",
    )


class CaseUserAction(Base):
    """Analyst feedback captured for Case Builder insights."""

    __tablename__ = "case_user_actions"
    __table_args__ = (
        Index("ix_case_user_actions_insight", "insight_id"),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    insight_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("case_insights.id", ondelete="CASCADE"),
        nullable=False,
    )
    action: Mapped[CaseUserActionType] = mapped_column(
        SQLEnum(CaseUserActionType, name="case_user_action_type"), nullable=False
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
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

    insight: Mapped[CaseInsight] = relationship(
        "CaseInsight", back_populates="user_actions"
    )


__all__ = [
    "Base",
    "Document",
    "Passage",
    "AppSetting",
    "DocumentAnnotation",
    "IngestionJob",
    "ResearchNote",
    "NoteEvidence",
    "CrossReference",
    "ContradictionSeed",
    "AgentTrail",
    "AgentStep",
    "TrailSource",
    "UserWatchlist",
    "WatchlistEvent",
    "GeoAncientPlace",
    "GeoModernLocation",
    "GeoPlaceVerse",
    "GeoGeometry",
    "GeoImage",
    "GeoPlace",
    "CaseSource",
    "CaseObject",
    "CaseEdge",
    "CaseInsight",
    "CaseUserAction",
    "CaseObjectType",
    "CaseEdgeKind",
    "CaseInsightType",
    "CaseUserActionType",
]
