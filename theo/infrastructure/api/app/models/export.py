"""Schemas describing API export payloads."""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from .base import APIModel, Passage
from .documents import DocumentDetailResponse
from .search import HybridSearchFilters

CitationStyleLiteral = Literal["csl-json", "apa", "chicago", "sbl", "bibtex"]


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
    topics: dict[str, Any] | list[str] | None = None
    primary_topic: str | None = None
    enrichment_version: int | None = None
    provenance_score: int | None = None


class SearchExportRow(APIModel):
    """Single row returned by the search export endpoint."""

    rank: int
    score: float | None = None
    passage: Passage
    document: ExportedDocumentSummary
    snippet: str | None = None


class SearchExportResponse(APIModel):
    """Payload returned by ``GET /export/search``."""

    query: str | None = None
    osis: str | None = None
    filters: HybridSearchFilters = Field(default_factory=HybridSearchFilters)
    mode: str | None = Field(default="results")
    cursor: str | None = None
    limit: int | None = None
    next_cursor: str | None = None
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
    cursor: str | None = None
    next_cursor: str | None = None
    total_documents: int
    total_passages: int
    documents: list[DocumentDetailResponse]


class ExportManifest(APIModel):
    """Common metadata written alongside exported records."""

    export_id: str
    schema_version: str
    created_at: datetime
    type: Literal["search", "documents", "citations"]
    filters: dict[str, Any]
    totals: dict[str, int]
    app_git_sha: str | None = None
    enrichment_version: int | None = None
    cursor: str | None = None
    next_cursor: str | None = None
    mode: str | None = None


class CitationExportRequest(APIModel):
    """Parameters accepted by the citation export endpoint."""

    style: CitationStyleLiteral = Field(
        default="apa", description="Citation style to render."
    )
    format: Literal["json", "ndjson", "csv", "markdown"] = Field(
        default="json", description="Output format to render."
    )
    document_ids: list[str] | None = Field(
        default=None,
        min_length=1,
        description="Explicit document identifiers to include.",
    )
    osis: str | None = Field(
        default=None,
        description="Optional OSIS reference to derive citations from verse mentions.",
    )
    filters: DocumentExportFilters = Field(
        default_factory=DocumentExportFilters,
        description="Document filters applied when expanding OSIS references.",
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        le=1000,
        description="Maximum number of verse mentions to inspect for each OSIS query.",
    )
    export_id: str | None = Field(
        default=None,
        description="Optional identifier to embed in the resulting manifest.",
    )


class DeliverableManifest(APIModel):
    """Metadata describing an export-ready deliverable payload."""

    export_id: str
    schema_version: str
    generated_at: datetime
    type: Literal["sermon", "transcript"]
    filters: dict[str, Any] = Field(default_factory=dict)
    git_sha: str | None = None
    model_preset: str | None = None
    sources: list[str] = Field(default_factory=list)


class DeliverableAsset(APIModel):
    """Single file artifact returned by a deliverable export."""

    format: Literal["markdown", "ndjson", "csv", "pdf"]
    filename: str
    media_type: str
    content: str | bytes


class DeliverablePackage(APIModel):
    """Complete payload for an export deliverable."""

    manifest: DeliverableManifest
    assets: list[DeliverableAsset]

    def get_asset(self, fmt: str) -> DeliverableAsset:
        for asset in self.assets:
            if asset.format == fmt:
                return asset
        raise ValueError(f"format {fmt!r} not present in deliverable")


def serialise_asset_content(content: str | bytes) -> str:
    """Return a JSON-safe string representation for deliverable content."""

    if isinstance(content, (bytes, bytearray)):
        return base64.b64encode(bytes(content)).decode("ascii")
    return content


class DeliverableResponse(APIModel):
    """API response describing an export deliverable job result."""

    export_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    manifest: DeliverableManifest | None = None
    manifest_path: str | None = None
    job_id: str | None = None
    assets: list["DeliverableDownload"]
    message: str | None = None


class DeliverableDownload(APIModel):
    """Metadata describing a persisted deliverable artifact."""

    format: Literal["markdown", "ndjson", "csv", "pdf"]
    filename: str
    media_type: str
    storage_path: str
    public_url: str | None = None
    signed_url: str | None = None
    size_bytes: int | None = None


class DeliverableRequest(APIModel):
    """Parameters accepted by the deliverable export endpoint."""

    type: Literal["sermon", "transcript"]
    formats: list[Literal["markdown", "ndjson", "csv", "pdf"]] = Field(
        default_factory=lambda: ["markdown"]
    )
    topic: str | None = None
    osis: str | None = None
    filters: HybridSearchFilters = Field(default_factory=HybridSearchFilters)
    model: str | None = None
    document_id: str | None = None


class ZoteroExportRequest(APIModel):
    """Parameters for exporting citations to Zotero."""

    document_ids: list[str] = Field(
        ...,
        description="Document identifiers to export to Zotero.",
    )
    api_key: str = Field(
        min_length=1,
        description="Zotero API key with write permissions.",
    )
    user_id: str | None = Field(
        default=None,
        description="Zotero user ID for personal library export.",
    )
    group_id: str | None = Field(
        default=None,
        description="Zotero group ID for group library export.",
    )


class ZoteroExportResponse(APIModel):
    """Response from Zotero export operation."""

    success: bool
    exported_count: int
    failed_count: int = 0
    errors: list[str] = Field(default_factory=list)
