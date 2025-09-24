"""Schemas describing API export payloads."""

from __future__ import annotations

from pydantic import Field

from .base import APIModel, Passage
from .documents import DocumentDetailResponse
from .search import HybridSearchFilters


class ExportedDocumentSummary(APIModel):
    """Metadata describing a document referenced by an export row."""

    id: str
    title: str | None = None
    source_type: str | None = None
    collection: str | None = None
    authors: list[str] | None = None
    doi: str | None = None
    venue: str | None = None
    year: int | None = None
    source_url: str | None = None


class SearchExportRow(APIModel):
    """Single row returned by the search export endpoint."""

    rank: int
    score: float | None = None
    passage: Passage
    document: ExportedDocumentSummary


class SearchExportResponse(APIModel):
    """Payload returned by ``GET /export/search``."""

    query: str | None = None
    osis: str | None = None
    filters: HybridSearchFilters = Field(default_factory=HybridSearchFilters)
    total_results: int
    results: list[SearchExportRow]


class DocumentExportFilters(APIModel):
    """Filters applied when exporting documents."""

    collection: str | None = Field(default=None)
    author: str | None = Field(default=None)
    source_type: str | None = Field(default=None)


class DocumentExportResponse(APIModel):
    """Bulk export payload for documents and their passages."""

    filters: DocumentExportFilters = Field(default_factory=DocumentExportFilters)
    include_passages: bool = True
    limit: int | None = Field(default=None, ge=1, le=1000)
    total_documents: int
    total_passages: int
    documents: list[DocumentDetailResponse]

