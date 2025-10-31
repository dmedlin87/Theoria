"""Pydantic schemas for MCP tool contracts."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class ToolRequestBase(BaseModel):
    """Base fields shared by all tool requests."""

    request_id: str = Field(..., description="Unique identifier supplied by the MCP client.")
    commit: bool = Field(
        default=False,
        description=(
            "When true, the server is allowed to persist mutations. Requests default to preview"
            " mode and must explicitly opt-in to writes."
        ),
    )


class ToolResponseBase(BaseModel):
    """Base fields shared by all tool responses."""

    request_id: str = Field(..., description="Echo of the originating request identifier.")
    run_id: str = Field(..., description="Server generated identifier for the tool execution.")
    commit: bool = Field(
        default=False,
        description="Echo of the commit flag used for the request.",
    )


class ToolErrorEnvelope(BaseModel):
    """Structured error response for deterministic client handling."""

    status: Literal["error"] = Field(default="error", description="Error status indicator.")
    error_code: str = Field(..., description="Machine-readable error code for client handling.")
    error_message: str = Field(..., description="Human-readable error description.")
    hint: str | None = Field(default=None, description="Optional hint for error resolution.")
    request_id: str = Field(..., description="Echo of the originating request identifier.")
    run_id: str = Field(..., description="Server generated identifier for the tool execution.")


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
    snippet_html: str | None = Field(
        default=None,
        description="HTML-rendered snippet with inline highlights for UI display.",
    )
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
    translation: str | None = Field(
        default=None,
        description="Optional translation code to use when retrieving scripture text.",
    )
    strategy: str = Field(
        default="concat",
        description="Aggregation strategy applied to the verse text (concat or harmonize).",
        pattern="^(concat|harmonize)$",
    )
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
    strategy: str = Field(..., description="Aggregation strategy applied to the verse text.")
    combined_text: str = Field(
        ..., description="Combined verse text generated according to the aggregation strategy."
    )
    citations: List[str] = Field(
        default_factory=list,
        description="Ordered OSIS citations represented in the aggregated text.",
    )
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
    window: Literal["week", "month", "quarter", "year"] = Field(
        default="month",
        description="Aggregation window (e.g. week, month, quarter, year).",
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
    timeline_html: str | None = Field(
        default=None,
        description="Simple HTML markup representing the rendered timeline.",
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
    limit: int = Field(
        default=5,
        ge=1,
        le=25,
        description="Maximum number of quotes to retrieve from the fuzzy search.",
    )


class QuoteRecord(BaseModel):
    """Information about a retrieved quote."""

    id: str = Field(..., description="Unique identifier of the quote.")
    osis_refs: List[str] = Field(default_factory=list, description="Associated OSIS references.")
    snippet: str = Field(..., description="Quote text or summary snippet.")
    snippet_html: str | None = Field(
        default=None,
        description="HTML formatted snippet with inline highlights.",
    )
    source_ref: str | None = Field(default=None, description="External reference identifier.")
    document_id: str | None = Field(default=None, description="Identifier of the originating document.")
    score: float | None = Field(
        default=None, description="Similarity score associated with the quote retrieval."
    )
    span_start: int | None = Field(
        default=None,
        description="Inclusive character offset for the highlighted span within the source text.",
    )
    span_end: int | None = Field(
        default=None,
        description="Exclusive character offset for the highlighted span within the source text.",
    )


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
    preview: Dict[str, Any] | None = Field(
        default=None,
        description="Preview metadata describing the note that would be created when commit=false.",
    )


class IndexRefreshRequest(ToolRequestBase):
    """Request the background refresh of an index."""

    sample_queries: int = Field(
        default=25,
        ge=1,
        le=500,
        description="Number of sample queries used to evaluate the refresh.",
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=200,
        description="Top-K parameter forwarded to the refresh evaluation routine.",
    )


class IndexRefreshResponse(ToolResponseBase):
    """Response payload for index refresh requests."""

    accepted: bool = Field(default=True, description="Indicates whether the refresh request was accepted.")
    message: str | None = Field(default=None, description="Optional human readable status message.")
    job: Dict[str, Any] | None = Field(
        default=None,
        description="Serialized job record returned when the refresh is committed.",
    )
    preview: Dict[str, Any] | None = Field(
        default=None,
        description="Parameters that would be enqueued when commit is false.",
    )


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
    preview: Dict[str, Any] | None = Field(
        default=None,
        description="Preview payload describing the evidence card when commit=false.",
    )


class ResearchRunMeta(BaseModel):
    """Metadata describing an orchestrated research run."""

    app: str = Field(..., description="Canonical application name (e.g. 'Theoria').")
    app_alias: List[str] = Field(
        default_factory=list,
        description="Alternate names used by clients when referring to the application.",
    )
    rubric_version: str = Field(..., description="Version identifier for the applied rubric.")
    schema_version: str = Field(..., description="Version identifier for the response schema.")
    model_final: str = Field(..., description="Model responsible for the final artifact synthesis.")
    models_used: List[str] = Field(
        default_factory=list,
        description="Ordered list of all models consulted during the run.",
    )
    file_ids_used: List[str] = Field(
        default_factory=list,
        description="Identifiers for uploaded files consulted during the run.",
    )
    web_used: bool = Field(..., description="Flag noting whether web search was used.")
    started_at: str = Field(..., description="ISO-8601 timestamp for when the run began.")
    completed_at: str = Field(..., description="ISO-8601 timestamp for when the run completed.")


class RunLogs(BaseModel):
    """Operational notes collected while orchestrating a run."""

    tools: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Structured logs for each tool invocation executed during the run.",
    )
    compromises: List[str] = Field(
        default_factory=list,
        description="Recorded deviations from the ideal execution path.",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-fatal issues surfaced during orchestration.",
    )
    notes: List[str] = Field(default_factory=list, description="Free-form run annotations.")


class EvidenceCardCitation(BaseModel):
    """Citation associated with an evidence card claim."""

    title: str = Field(..., description="Title of the cited work.")
    url: str = Field(..., description="Canonical URL for the citation.")
    source_type: Literal["primary", "secondary", "tertiary"] = Field(
        ...,
        description="Classification of the cited work.",
    )
    accessed: str = Field(..., description="ISO formatted date indicating when the source was accessed.")
    excerpt: str = Field(..., description="Excerpt copied from the cited work.")


class EvidenceCardStabilityComponents(BaseModel):
    """Breakdown of stability inputs for an evidence card."""

    attestation: float | None = Field(
        default=None,
        description="Attestation strength score contributing to stability.",
    )
    consensus: float | None = Field(
        default=None,
        description="Scholarly consensus score contributing to stability.",
    )
    recency_risk: float | None = Field(
        default=None,
        description="Risk introduced by relying on recent sources.",
    )
    textual_variants: float | None = Field(
        default=None,
        description="Instability introduced by textual variants or manuscript issues.",
    )


class EvidenceCardStability(BaseModel):
    """Aggregated stability information for an evidence card."""

    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Composite stability score for the claim (0–1).",
    )
    components: EvidenceCardStabilityComponents = Field(
        default_factory=EvidenceCardStabilityComponents,
        description="Component-level breakdown underpinning the stability score.",
    )


class EvidenceCardArtifact(BaseModel):
    """Structured claim analysis captured as an evidence card."""

    id: str = Field(..., description="Unique identifier for the evidence card.")
    claim: str = Field(..., description="Precise articulation of the claim under evaluation.")
    mode: Literal["Apologetic", "Neutral", "Skeptical"] = Field(
        default="Neutral",
        description="Perspective adopted while summarising the evidence.",
    )
    citations: List[EvidenceCardCitation] = Field(
        default_factory=list,
        description="Ordered list of citations supporting the claim.",
    )
    evidence_points: List[str] = Field(
        default_factory=list,
        description="Key evidence statements derived from the cited sources.",
    )
    counter_evidence: List[str] = Field(
        default_factory=list,
        description="Evidence challenging or complicating the claim.",
    )
    stability: EvidenceCardStability = Field(
        ...,
        description="Overall stability assessment for the claim.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence in the presented synthesis (0–1).",
    )
    open_questions: List[str] = Field(
        default_factory=list,
        description="Outstanding research questions surfaced during synthesis.",
    )
    rubric_version: str = Field(..., description="Rubric version applied while producing the card.")
    schema_version: str = Field(..., description="Schema version describing the evidence card payload.")


class ContradictionGraphEdge(BaseModel):
    """Edge describing relationships within a contradiction graph."""

    from_: str = Field(
        alias="from",
        description="Origin node identifier for the graph edge.",
    )
    to: str = Field(..., description="Destination node identifier for the graph edge.")
    weight: float | None = Field(
        default=None,
        description="Optional weighting for the edge signalling conflict strength.",
    )

    model_config = {
        "populate_by_name": True,
    }


class ContradictionArtifact(BaseModel):
    """Description of an identified textual contradiction."""

    id: str = Field(..., description="Unique identifier for the contradiction artifact.")
    passage_a: str = Field(..., description="First passage involved in the contradiction.")
    passage_b: str = Field(..., description="Second passage involved in the contradiction.")
    conflict_type: Literal[
        "chronology",
        "genealogy",
        "event",
        "speech",
        "law",
        "number",
        "title",
    ] = Field(..., description="Type of conflict represented by the contradiction.")
    notes: str = Field(..., description="Narrative explanation describing the contradiction.")
    graph_edges: List[ContradictionGraphEdge] = Field(
        default_factory=list,
        description="Edges connecting passages or claims implicated in the contradiction graph.",
    )


class ScholarDigestArtifact(BaseModel):
    """Summary of scholarly viewpoints for a research topic."""

    id: str = Field(..., description="Unique identifier for the scholar digest artifact.")
    topic: str = Field(..., description="Topic addressed by the digest.")
    thesis: str = Field(..., description="High-level thesis articulated for the topic.")
    sources: List[str] = Field(
        default_factory=list,
        description="List of key sources underpinning the digest.",
    )
    summary: str = Field(..., description="Synthesis of scholarly perspectives.")
    gaps: List[str] = Field(
        default_factory=list,
        description="Known gaps or uncertainties within the scholarly coverage.",
    )
    next_actions: List[str] = Field(
        default_factory=list,
        description="Suggested follow-up actions to progress the research topic.",
    )


class IngestionRecordArtifact(BaseModel):
    """Operational record capturing the state of an ingested source."""

    id: str = Field(..., description="Unique identifier for the ingestion record artifact.")
    file_id: str = Field(..., description="Identifier of the ingested file within Theo storage.")
    source_url: str = Field(..., description="Source URL for the ingested document.")
    status: Literal["acquired", "parsed", "indexed", "failed"] = Field(
        ...,
        description="Current processing status of the ingested document.",
    )
    notes: str = Field(..., description="Additional context or error information for the ingestion run.")


ResearchArtifact = Union[
    EvidenceCardArtifact,
    ContradictionArtifact,
    ScholarDigestArtifact,
    IngestionRecordArtifact,
]


class ResearchRunEnvelope(BaseModel):
    """Top-level response contract for orchestrated research runs."""

    run_meta: ResearchRunMeta = Field(
        ...,
        description="Metadata describing the research run context and configuration.",
    )
    artifacts: List[ResearchArtifact] = Field(
        default_factory=list,
        description="Artifacts generated during the research run.",
    )
    run_logs: RunLogs = Field(
        default_factory=RunLogs,
        description="Operational logs recorded while running the research workflow.",
    )
    validation_errors: List[str] = Field(
        default_factory=list,
        description="Schema validation errors encountered while assembling the response.",
    )
