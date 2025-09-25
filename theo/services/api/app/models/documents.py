"""Document schemas for API responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from .base import APIModel, Passage


class DocumentIngestResponse(APIModel):
    document_id: str
    status: str


class UrlIngestRequest(APIModel):
    url: str
    source_type: str | None = None
    frontmatter: dict[str, Any] | None = None

class DocumentSummary(APIModel):
    id: str
    title: str | None = None
    source_type: str | None = None
    collection: str | None = None
    authors: list[str] | None = None
    doi: str | None = None
    venue: str | None = None
    year: int | None = None
    created_at: datetime
    updated_at: datetime
    provenance_score: int | None = None


class DocumentDetailResponse(DocumentSummary):
    source_url: str | None = None
    channel: str | None = None
    video_id: str | None = None
    duration_seconds: int | None = None
    storage_path: str | None = None
    abstract: str | None = None
    topics: dict[str, Any] | list[str] | None = None
    enrichment_version: int | None = None
    primary_topic: str | None = None
    metadata: dict[str, Any] | None = Field(default=None, alias="meta")
    passages: list[Passage] = Field(default_factory=list)
    annotations: list["DocumentAnnotationResponse"] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class DocumentListResponse(APIModel):
    items: list[DocumentSummary]
    total: int
    limit: int
    offset: int


class DocumentPassagesResponse(APIModel):
    document_id: str
    passages: list[Passage]
    total: int
    limit: int
    offset: int


class DocumentAnnotationResponse(APIModel):
    id: str
    document_id: str
    body: str
    created_at: datetime
    updated_at: datetime


class DocumentAnnotationCreate(APIModel):
    body: str


class DocumentUpdateRequest(APIModel):
    title: str | None = None
    collection: str | None = None
    authors: list[str] | None = None
    source_type: str | None = None
    abstract: str | None = None
    metadata: dict[str, Any] | None = Field(default=None, alias="meta")

DocumentDetailResponse.model_rebuild()
