"""Document schemas for API responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import ConfigDict, Field, field_validator, model_validator

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


AnnotationType = Literal["claim", "evidence", "question", "note"]


class DocumentAnnotationResponse(APIModel):
    id: str
    document_id: str
    type: AnnotationType
    body: str
    stance: str | None = None
    passage_ids: list[str] = Field(default_factory=list)
    group_id: str | None = None
    metadata: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None
    legacy: bool = False
    created_at: datetime
    updated_at: datetime


class DocumentAnnotationCreate(APIModel):
    type: AnnotationType | None = Field(
        default=None, description="Structured annotation type"
    )
    text: str | None = Field(
        default=None, description="Primary text body for the annotation"
    )
    stance: str | None = Field(
        default=None, description="Optional stance label for the annotation"
    )
    passage_ids: list[str] = Field(
        default_factory=list,
        description="Passage identifiers referenced by this annotation",
    )
    group_id: str | None = Field(
        default=None, description="Shared identifier to link related annotations"
    )
    metadata: dict[str, Any] | None = Field(
        default=None, description="Arbitrary structured metadata for the annotation"
    )
    body: str | None = Field(
        default=None,
        description="Legacy free-form annotation text (alias for text)",
    )

    @field_validator("passage_ids", mode="before")
    @classmethod
    def _normalise_passage_ids(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            candidate = value.strip()
            return [candidate] if candidate else []
        cleaned: list[str] = []
        for item in value:
            candidate = str(item).strip()
            if candidate:
                cleaned.append(candidate)
        return cleaned

    @field_validator("metadata", mode="before")
    @classmethod
    def _ensure_metadata_dict(
        cls, value: Any
    ) -> dict[str, Any] | None:  # pragma: no cover - defensive
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        raise TypeError("metadata must be an object")

    @model_validator(mode="after")
    def _coerce_text(self) -> "DocumentAnnotationCreate":
        text = (self.text or "").strip()
        body = (self.body or "").strip()
        if text and not body:
            self.body = text
        elif body and not text:
            self.text = body
        elif text and body and text != body:
            # Prefer explicit text when both values are supplied.
            self.body = text
        final_text = (self.text or "").strip()
        if not final_text:
            raise ValueError("Annotation text cannot be empty")
        self.text = final_text
        self.body = final_text
        if self.type is None:
            self.type = "note"
        return self


class DocumentUpdateRequest(APIModel):
    title: str | None = None
    collection: str | None = None
    authors: list[str] | None = None
    source_type: str | None = None
    abstract: str | None = None
    metadata: dict[str, Any] | None = Field(default=None, alias="meta")


DocumentDetailResponse.model_rebuild()
