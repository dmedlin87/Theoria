"""Document schemas for API responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from urllib.parse import urlparse

from pydantic import ConfigDict, Field, field_validator

from ..core.settings import get_settings

from .base import APIModel, Passage


class DocumentIngestResponse(APIModel):
    document_id: str
    status: str


class UrlIngestRequest(APIModel):
    url: str = Field(max_length=2048)
    source_type: str | None = None
    frontmatter: dict[str, Any] | None = None

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("URL must include a scheme and host")

        settings = get_settings()
        scheme = parsed.scheme.lower()
        blocked = {item.lower() for item in settings.ingest_url_blocked_schemes}
        if scheme in blocked:
            raise ValueError("URL scheme is not allowed")

        allowed = {item.lower() for item in settings.ingest_url_allowed_schemes}
        if allowed and scheme not in allowed:
            raise ValueError("URL scheme is not allowed")

        return value


class SimpleIngestRequest(APIModel):
    sources: list[str] = Field(min_length=1)
    mode: Literal["api", "worker"] = "api"
    batch_size: int = Field(default=10, ge=1)
    metadata: dict[str, Any] | None = None
    post_batch: list[str] | None = None
    dry_run: bool = False

    @field_validator("sources", mode="before")
    @classmethod
    def _normalise_sources(cls, value: object) -> list[str]:
        if isinstance(value, str):
            segments = [segment.strip() for segment in value.splitlines() if segment.strip()]
            if not segments:
                raise ValueError("At least one source is required")
            return segments
        if isinstance(value, (list, tuple, set)):
            segments = [str(item).strip() for item in value if str(item).strip()]
            if not segments:
                raise ValueError("At least one source is required")
            return segments
        raise ValueError("Sources must be provided as a list or newline-delimited string")

    @field_validator("post_batch", mode="before")
    @classmethod
    def _normalise_post_batch(cls, value: object) -> list[str] | None:
        if value in (None, ""):
            return None
        if isinstance(value, str):
            segments = [segment.strip() for segment in value.split(",") if segment.strip()]
            return segments or None
        if isinstance(value, (list, tuple, set)):
            segments = [str(item).strip() for item in value if str(item).strip()]
            return segments or None
        raise ValueError("Invalid post-batch configuration")


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
