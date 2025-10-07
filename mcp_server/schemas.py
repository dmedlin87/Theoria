"""Pydantic schemas for MCP tool contracts."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolRequestBase(BaseModel):
    """Base fields shared by all tool requests."""

    request_id: str = Field(..., description="Unique identifier supplied by the MCP client.")
    dry_run: bool = Field(
        default=False,
        description="When true, the server performs validation without mutating persistent state.",
    )


class ToolResponseBase(BaseModel):
    """Base fields shared by all tool responses."""

    request_id: str = Field(..., description="Echo of the originating request identifier.")
    run_id: str = Field(..., description="Server generated identifier for the tool execution.")
    dry_run: bool = Field(
        default=False,
        description="Indicates whether the tool was executed in dry-run mode.",
    )


class SearchLibraryRequest(ToolRequestBase):
    """Search the Theo library for passages or documents."""

    query: str = Field(..., description="Full text query or OSIS reference to search for.")
    filters: Dict[str, Any] | None = Field(
        default=None,
        description="Optional search filters such as collection, author, or tradition.",
    )
    limit: int = Field(default=10, ge=1, le=100, description="Maximum number of results to return.")


class SearchLibraryResult(BaseModel):
    """Single search hit returned by the library search tool."""

    document_id: str = Field(..., description="Identifier of the document containing the hit.")
    title: str | None = Field(default=None, description="Title of the source document.")
    snippet: str = Field(..., description="Relevant excerpt for the match.")
    osis: str | None = Field(default=None, description="Primary OSIS reference for the hit.")
    score: float | None = Field(default=None, description="Relevance score assigned by the retriever.")


class SearchLibraryResponse(ToolResponseBase):
    """Response payload for a library search invocation."""

    results: List[SearchLibraryResult] = Field(
        default_factory=list,
        description="Ranked list of search results (empty for stub implementation).",
    )
    debug: Dict[str, Any] | None = Field(
        default=None,
        description="Optional diagnostic information returned by the backend search stack.",
    )


class AggregateVersesRequest(ToolRequestBase):
    """Aggregate verse mentions across the Theo corpus."""

    osis: str = Field(..., description="OSIS passage to aggregate mentions for.")
    filters: Dict[str, Any] | None = Field(
        default=None,
        description="Optional filters limiting the aggregation scope.",
    )


class VerseAggregateBucket(BaseModel):
    """Aggregated mention information for a single verse bucket."""

    label: str = Field(..., description="Human readable grouping label (e.g. collection name).")
    count: int = Field(..., ge=0, description="Number of mentions represented in the bucket.")
    document_ids: List[str] = Field(
        default_factory=list,
        description="Unique identifiers for documents contributing to the bucket.",
    )


class AggregateVersesResponse(ToolResponseBase):
    """Response payload for the verse aggregation tool."""

    osis: str = Field(..., description="Echo of the requested OSIS passage.")
    buckets: List[VerseAggregateBucket] = Field(
        default_factory=list,
        description="Aggregated buckets (empty for the stub implementation).",
    )
    total_mentions: int = Field(
        default=0,
        ge=0,
        description="Total mentions counted across all buckets.",
    )


class GetTimelineRequest(ToolRequestBase):
    """Retrieve a timeline of mentions for a verse."""

    osis: str = Field(..., description="Passage identifier to build a timeline for.")
    window: str = Field(
        default="month",
        description="Aggregation window (e.g. week, month, quarter, year).",
        pattern="^(week|month|quarter|year)$",
    )
    limit: int = Field(
        default=36,
        ge=1,
        le=240,
        description="Maximum number of timeline buckets to return.",
    )
    filters: Dict[str, Any] | None = Field(
        default=None,
        description="Optional filters applied before aggregation.",
    )


class TimelineBucket(BaseModel):
    """Single timeline bucket summarising mentions in a window."""

    label: str = Field(..., description="Human readable window label.")
    start: str = Field(..., description="ISO formatted inclusive window start.")
    end: str = Field(..., description="ISO formatted exclusive window end.")
    count: int = Field(..., ge=0, description="Number of mentions captured in the window.")
    document_ids: List[str] = Field(
        default_factory=list,
        description="Document identifiers represented in the bucket.",
    )


class GetTimelineResponse(ToolResponseBase):
    """Response payload for the timeline aggregation tool."""

    osis: str = Field(..., description="Echo of the requested OSIS passage.")
    window: str = Field(..., description="Window used to aggregate the timeline.")
    buckets: List[TimelineBucket] = Field(
        default_factory=list,
        description="Timeline buckets (empty for stub implementation).",
    )
    total_mentions: int = Field(
        default=0,
        ge=0,
        description="Total mentions captured across the returned timeline buckets.",
    )


class QuoteLookupRequest(ToolRequestBase):
    """Lookup transcript quotes related to a passage or identifier."""

    osis: str | None = Field(
        default=None,
        description="Optional OSIS passage anchor for the quote search.",
    )
    quote_ids: List[str] | None = Field(
        default=None,
        description="Specific quote identifiers to retrieve.",
    )
    source_ref: str | None = Field(
        default=None,
        description="Optional external source reference to look up.",
    )


class QuoteRecord(BaseModel):
    """Information about a retrieved quote."""

    id: str = Field(..., description="Unique identifier of the quote.")
    osis_refs: List[str] = Field(default_factory=list, description="Associated OSIS references.")
    snippet: str = Field(..., description="Quote text or summary snippet.")
    source_ref: str | None = Field(default=None, description="External reference identifier.")
    document_id: str | None = Field(default=None, description="Identifier of the originating document.")


class QuoteLookupResponse(ToolResponseBase):
    """Response payload for quote lookups."""

    quotes: List[QuoteRecord] = Field(
        default_factory=list,
        description="Retrieved quotes (empty for stub implementation).",
    )
    total: int = Field(default=0, ge=0, description="Total quotes returned.")


class NoteWriteRequest(ToolRequestBase):
    """Create or update a research note."""

    osis: str = Field(..., description="Passage anchor for the research note.")
    body: str = Field(..., description="Primary body text of the note.")
    title: str | None = Field(default=None, description="Optional note title.")
    stance: str | None = Field(default=None, description="Stance classification for the note.")
    claim_type: str | None = Field(default=None, description="Type of claim the note represents.")
    tags: List[str] | None = Field(default=None, description="Optional tags applied to the note.")
    evidences: List[Dict[str, Any]] | None = Field(
        default=None,
        description="Evidence entries attached to the note.",
    )


class NoteWriteResponse(ToolResponseBase):
    """Response payload for note creation or updates."""

    note_id: str | None = Field(default=None, description="Identifier of the persisted note.")
    status: str = Field(default="accepted", description="Execution status for the request.")


class IndexRefreshRequest(ToolRequestBase):
    """Request the background refresh of an index."""

    index_name: str = Field(..., description="Identifier for the index to refresh.")
    priority: str | None = Field(default=None, description="Optional priority hint for the refresh job.")


class IndexRefreshResponse(ToolResponseBase):
    """Response payload for index refresh requests."""

    accepted: bool = Field(default=True, description="Indicates whether the refresh request was accepted.")
    message: str | None = Field(default=None, description="Optional human readable status message.")


class SourceRegistryListRequest(ToolRequestBase):
    """List registered MCP sources."""

    collection: str | None = Field(
        default=None,
        description="Optional collection filter limiting the registry results.",
    )


class SourceRegistryEntry(BaseModel):
    """Single entry from the MCP source registry."""

    id: str = Field(..., description="Unique identifier for the source.")
    name: str = Field(..., description="Human readable source name.")
    description: str | None = Field(default=None, description="Optional source description.")
    url: str | None = Field(default=None, description="Canonical URL for the source.")


class SourceRegistryListResponse(ToolResponseBase):
    """Response payload for source registry listings."""

    sources: List[SourceRegistryEntry] = Field(
        default_factory=list,
        description="Registered sources (empty for stub implementation).",
    )
    total: int = Field(default=0, ge=0, description="Total sources returned.")


class EvidenceCardCreateRequest(ToolRequestBase):
    """Create a new evidence card anchored to a passage or claim."""

    osis: str = Field(..., description="Primary passage anchor for the evidence card.")
    claim_summary: str = Field(..., description="Short description of the claim supported by the evidence.")
    evidence: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured evidence payload mirrored from the Theo API.",
    )
    tags: List[str] | None = Field(default=None, description="Optional tags applied to the evidence card.")


class EvidenceCardCreateResponse(ToolResponseBase):
    """Response payload for evidence card creation."""

    evidence_id: str | None = Field(
        default=None,
        description="Identifier of the created evidence card when persistence succeeds.",
    )
    status: str = Field(default="accepted", description="Execution status for the request.")
