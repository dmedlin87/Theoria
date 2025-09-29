"""Database models for Theo Engine."""

from __future__ import annotations

from datetime import UTC, datetime
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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from ..core.settings import get_settings
from .types import TSVectorType, VectorType


class Document(Base):
    """Source artifact ingested into the system."""

    __tablename__ = "documents"

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
    video: Mapped["Video | None"] = relationship(
        "Video",
        back_populates="document",
        cascade="all, delete-orphan",
        uselist=False,
        single_parent=True,
    )


class Passage(Base):
    """Chunked content extracted from a document."""

    __tablename__ = "passages"

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

    document: Mapped[Document | None] = relationship("Document")


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
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


class ChatSession(Base):
    """Persistent state for a conversational chat session."""

    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    stance: Mapped[str | None] = mapped_column(String, nullable=True)
    mode_id: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    memory_snippets: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    linked_document_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    preferences: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    last_turn_at: Mapped[datetime | None] = mapped_column(
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

    messages: Mapped[list["ChatSessionMessage"]] = relationship(
        "ChatSessionMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatSessionMessage.sequence",
    )


class ChatSessionMessage(Base):
    """Persisted transcript entry for a chat session."""

    __tablename__ = "chat_session_messages"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    session: Mapped[ChatSession] = relationship("ChatSession", back_populates="messages")


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


__all__ = [
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
    "ChatSession",
    "ChatSessionMessage",
    "UserWatchlist",
    "WatchlistEvent",
    "GeoAncientPlace",
    "GeoModernLocation",
    "GeoPlaceVerse",
    "GeoGeometry",
    "GeoImage",
    "GeoPlace",
]
