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


__all__ = ["Document", "Passage"]
