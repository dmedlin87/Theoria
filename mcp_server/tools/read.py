"""Handlers for MCP read/research tools."""

from __future__ import annotations

import html
import logging
import re
from collections import OrderedDict
from contextlib import contextmanager
from typing import Annotated, Any, Iterable, Iterator, Sequence
from uuid import uuid4

from fastapi import Header
from opentelemetry import trace
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import schemas
from ..security import WriteSecurityError, get_read_security_policy
from ..validators import (
    validate_end_user_id,
    validate_filters,
    validate_osis_reference,
    validate_query,
)
from theo.application.facades.database import get_session
from theo.services.api.app.db.models import Document, TranscriptQuote
from theo.services.api.app.models.search import (
    HybridSearchFilters,
    HybridSearchRequest,
    HybridSearchResult,
)
from theo.services.api.app.models.verses import VerseMentionsFilters
from theo.services.api.app.research.scripture import fetch_passage
from theo.services.api.app.retriever.hybrid import hybrid_search
from theo.services.api.app.retriever.verses import get_verse_timeline

LOGGER = logging.getLogger(__name__)
_TRACER = trace.get_tracer("theo.mcp.read")


@contextmanager
def _session_scope() -> Iterator[Session]:
    """Yield a managed SQLAlchemy session tied to FastAPI settings."""

    session_gen = get_session()
    session = next(session_gen)
    try:
        yield session
    finally:
        try:
            next(session_gen)
        except StopIteration:
            pass


@contextmanager
def _tool_instrumentation(
    tool: str, request: schemas.ToolRequestBase, end_user_id: str
) -> Iterator[tuple[str, Any]]:
    """Context manager adding span attributes and structured logging."""

    run_id = str(uuid4())
    with _TRACER.start_as_current_span(f"mcp.{tool}") as span:
        span.set_attribute("tool.name", tool)
        span.set_attribute("tool.request_id", request.request_id)
        span.set_attribute("tool.end_user_id", end_user_id)
        span.set_attribute("tool.commit", request.commit)
        LOGGER.info(
            "mcp.tool.invoked",
            extra={
                "event": f"mcp.{tool}",
                "tool": tool,
                "request_id": request.request_id,
                "end_user_id": end_user_id,
                "commit": request.commit,
                "run_id": run_id,
            },
        )
        yield run_id, span


def _render_snippet_html(
    snippet: str, highlights: Sequence[str] | None, query: str | None
) -> str:
    """Generate inline HTML with highlighted tokens."""

    escaped = html.escape(snippet)
    tokens: list[str] = []
    if highlights:
        tokens.extend(highlights)
    elif query:
        tokens.extend(token.strip() for token in re.split(r"\s+", query) if token.strip())
    if not tokens:
        return f"<p>{escaped}</p>"

    # Preserve insertion order and prevent duplicate replacements.
    normalized = OrderedDict((token.lower(), token) for token in tokens)
    pattern = re.compile("|".join(re.escape(token) for token in normalized.values()), re.IGNORECASE)

    def _highlight(match: re.Match[str]) -> str:
        return f"<mark>{match.group(0)}</mark>"

    highlighted = pattern.sub(_highlight, escaped)
    return f"<p>{highlighted}</p>"


def _select_search_filters(filters: dict[str, Any] | None) -> HybridSearchFilters:
    filters = filters or {}
    supported: dict[str, Any] = {
        key: filters.get(key)
        for key in (
            "collection",
            "author",
            "source_type",
            "theological_tradition",
            "topic_domain",
        )
        if filters.get(key) is not None
    }
    return HybridSearchFilters(**supported)


async def search_library(
    request: schemas.SearchLibraryRequest,
    end_user_id: Annotated[str, Header(alias="X-End-User-Id")],
) -> schemas.SearchLibraryResponse:
    """Execute hybrid search and project results to the MCP schema."""

    # Validate inputs
    validated_user_id = validate_end_user_id(end_user_id)
    validate_query(request.query)
    validate_filters(request.filters)

    # Enforce rate limiting
    policy = get_read_security_policy()
    try:
        policy.enforce_rate_limit("search_library", validated_user_id)
    except WriteSecurityError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    with _tool_instrumentation("search_library", request, validated_user_id) as (
        run_id,
        span,
    ):
        search_request = HybridSearchRequest(
            query=request.query,
            osis=request.filters.get("osis") if request.filters else None,
            filters=_select_search_filters(request.filters),
            k=request.limit,
        )
        with _session_scope() as session:
            results = hybrid_search(session, search_request)

        contract_results: list[schemas.SearchLibraryResult] = []
        for result in results:
            snippet_html = _render_snippet_html(
                result.snippet,
                result.highlights,
                request.query,
            )
            contract_results.append(
                schemas.SearchLibraryResult(
                    document_id=result.document_id,
                    title=result.document_title,
                    snippet=result.snippet,
                    snippet_html=snippet_html,
                    osis=result.osis_ref,
                    score=result.score,
                )
            )
        span.set_attribute("tool.result_count", len(contract_results))
        return schemas.SearchLibraryResponse(
            request_id=request.request_id,
            run_id=run_id,
            commit=request.commit,
            results=contract_results,
            debug={"query": request.query, "filters": request.filters},
        )


def _aggregate_text(
    verses: Iterable[Any], strategy: str
) -> tuple[str, list[str]]:
    """Return combined verse text and OSIS references."""

    citations: list[str] = []
    lines: list[str] = []
    seen: set[str] = set()
    for verse in verses:
        citations.append(verse.osis)
        text = verse.text.strip()
        if strategy == "harmonize":
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
        lines.append(text)
    if strategy == "harmonize":
        combined = " / ".join(lines)
    else:
        combined = "\n\n".join(lines)
    return combined, citations


async def aggregate_verses(
    request: schemas.AggregateVersesRequest,
    end_user_id: Annotated[str, Header(alias="X-End-User-Id")],
) -> schemas.AggregateVersesResponse:
    """Aggregate scripture text for the requested OSIS range."""

    # Validate inputs
    validated_user_id = validate_end_user_id(end_user_id)
    validate_osis_reference(request.osis)

    # Enforce rate limiting
    policy = get_read_security_policy()
    try:
        policy.enforce_rate_limit("aggregate_verses", validated_user_id)
    except WriteSecurityError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    with _tool_instrumentation("aggregate_verses", request, validated_user_id) as (
        run_id,
        span,
    ):
        verses = fetch_passage(request.osis, translation=request.translation)
        combined_text, citations = _aggregate_text(verses, request.strategy)
        span.set_attribute("tool.citation_count", len(citations))
        return schemas.AggregateVersesResponse(
            request_id=request.request_id,
            run_id=run_id,
            commit=request.commit,
            osis=request.osis,
            strategy=request.strategy,
            combined_text=combined_text,
            citations=citations,
            buckets=[],
            total_mentions=0,
        )


def _build_timeline_filters(filters: dict[str, Any] | None) -> VerseMentionsFilters:
    filters = filters or {}
    supported = {
        key: filters.get(key)
        for key in ("source_type", "collection", "author")
        if filters.get(key) is not None
    }
    return VerseMentionsFilters(**supported)


def _render_timeline_html(buckets: Sequence[schemas.TimelineBucket]) -> str:
    if not buckets:
        return "<p>No timeline data available.</p>"
    items = []
    for bucket in buckets:
        items.append(
            (
                "<li><strong>{label}</strong>: {count} mentions "
                "<span data-start=\"{start}\" data-end=\"{end}\"></span></li>"
            ).format(
                label=html.escape(bucket.label),
                count=bucket.count,
                start=html.escape(bucket.start),
                end=html.escape(bucket.end),
            )
        )
    return "<ul class=\"timeline\">" + "".join(items) + "</ul>"


async def get_timeline(
    request: schemas.GetTimelineRequest,
    end_user_id: Annotated[str, Header(alias="X-End-User-Id")],
) -> schemas.GetTimelineResponse:
    """Return aggregated timeline information for an OSIS passage."""

    # Validate inputs
    validated_user_id = validate_end_user_id(end_user_id)
    validate_osis_reference(request.osis)
    validate_filters(request.filters)

    # Enforce rate limiting
    policy = get_read_security_policy()
    try:
        policy.enforce_rate_limit("get_timeline", validated_user_id)
    except WriteSecurityError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    with _tool_instrumentation("get_timeline", request, validated_user_id) as (
        run_id,
        span,
    ):
        filters = _build_timeline_filters(request.filters)
        with _session_scope() as session:
            timeline = get_verse_timeline(
                session,
                request.osis,
                window=request.window,
                limit=request.limit,
                filters=filters,
            )
        buckets: list[schemas.TimelineBucket] = []
        for item in timeline.buckets:
            buckets.append(
                schemas.TimelineBucket(
                    label=item.label,
                    start=item.start.isoformat(),
                    end=item.end.isoformat(),
                    count=item.count,
                    document_ids=item.document_ids,
                )
            )
        html_markup = _render_timeline_html(buckets)
        span.set_attribute("tool.bucket_count", len(buckets))
        return schemas.GetTimelineResponse(
            request_id=request.request_id,
            run_id=run_id,
            commit=request.commit,
            osis=request.osis,
            window=request.window,
            buckets=buckets,
            total_mentions=timeline.total_mentions,
            timeline_html=html_markup,
        )


def _quote_from_result(result: HybridSearchResult) -> schemas.QuoteRecord:
    return schemas.QuoteRecord(
        id=result.id,
        osis_refs=[ref for ref in [result.osis_ref] if ref],
        snippet=result.snippet,
        snippet_html=_render_snippet_html(result.snippet, result.highlights, None),
        source_ref=result.meta.get("source_ref") if result.meta else None,
        document_id=result.document_id,
        score=result.score,
        span_start=result.start_char,
        span_end=result.end_char,
    )


def _quote_from_model(quote: TranscriptQuote) -> schemas.QuoteRecord:
    snippet = quote.quote_md
    osis_refs = quote.osis_refs or []
    return schemas.QuoteRecord(
        id=quote.id,
        osis_refs=list(osis_refs),
        snippet=snippet,
        snippet_html=_render_snippet_html(snippet, None, None),
        source_ref=quote.source_ref,
        document_id=quote.video_id or quote.segment_id,
        score=None,
        span_start=None,
        span_end=None,
    )


async def quote_lookup(
    request: schemas.QuoteLookupRequest,
    end_user_id: Annotated[str, Header(alias="X-End-User-Id")],
) -> schemas.QuoteLookupResponse:
    """Retrieve transcript quote snippets using fuzzy passage search."""

    # Validate inputs
    validated_user_id = validate_end_user_id(end_user_id)
    if request.osis:
        validate_osis_reference(request.osis)
    from ..validators import validate_array_length
    validate_array_length(request.quote_ids, "quote_ids", max_length=50)

    # Enforce rate limiting
    policy = get_read_security_policy()
    try:
        policy.enforce_rate_limit("quote_lookup", validated_user_id)
    except WriteSecurityError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    with _tool_instrumentation("quote_lookup", request, validated_user_id) as (
        run_id,
        span,
    ):
        quotes: list[schemas.QuoteRecord] = []
        with _session_scope() as session:
            if request.quote_ids:
                stmt = select(TranscriptQuote).where(
                    TranscriptQuote.id.in_(request.quote_ids)
                )
                for quote in session.scalars(stmt):
                    quotes.append(_quote_from_model(quote))
            else:
                search_request = HybridSearchRequest(
                    query=request.source_ref,
                    osis=request.osis,
                    filters=HybridSearchFilters(),
                    k=request.limit,
                )
                results = hybrid_search(session, search_request)
                quotes = [_quote_from_result(item) for item in results]
        span.set_attribute("tool.quote_count", len(quotes))
        return schemas.QuoteLookupResponse(
            request_id=request.request_id,
            run_id=run_id,
            commit=request.commit,
            quotes=quotes,
            total=len(quotes),
        )


def _summarise_source_entry(
    *,
    document_id: str,
    title: str | None,
    collection: str | None,
    source_type: str | None,
    abstract: str | None,
    source_url: str | None,
) -> tuple[str, str | None, str | None]:
    """Return the display name and description for a source registry entry."""

    name = title or collection or document_id
    description_parts: list[str] = []
    if abstract:
        cleaned = abstract.strip()
        if cleaned:
            description_parts.append(cleaned)
    if collection:
        description_parts.append(f"Collection: {collection}")
    if source_type:
        description_parts.append(f"Source type: {source_type}")

    description: str | None = None
    if description_parts:
        combined = " ".join(description_parts).strip()
        if combined:
            description = combined if len(combined) <= 280 else combined[:277].rstrip() + "..."
    return name, description, source_url


async def source_registry_list(
    request: schemas.SourceRegistryListRequest,
    end_user_id: Annotated[str, Header(alias="X-End-User-Id")],
) -> schemas.SourceRegistryListResponse:
    """Return source registry entries backed by Theo documents."""

    # Validate inputs
    validated_user_id = validate_end_user_id(end_user_id)

    # Enforce rate limiting
    policy = get_read_security_policy()
    try:
        policy.enforce_rate_limit("source_registry_list", validated_user_id)
    except WriteSecurityError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    with _tool_instrumentation("source_registry_list", request, validated_user_id) as (
        run_id,
        span,
    ):
        with _session_scope() as session:
            stmt = select(
                Document.id,
                Document.title,
                Document.collection,
                Document.source_type,
                Document.abstract,
                Document.source_url,
            ).order_by(Document.created_at.desc())
            count_stmt = select(func.count()).select_from(Document)
            if request.collection:
                stmt = stmt.where(Document.collection == request.collection)
                count_stmt = count_stmt.where(Document.collection == request.collection)
            rows = session.execute(stmt.limit(100)).all()
            total = session.execute(count_stmt).scalar() or 0

        entries: list[schemas.SourceRegistryEntry] = []
        for (
            document_id,
            title,
            collection,
            source_type,
            abstract,
            source_url,
        ) in rows:
            name, description, url = _summarise_source_entry(
                document_id=document_id,
                title=title,
                collection=collection,
                source_type=source_type,
                abstract=abstract,
                source_url=source_url,
            )
            entries.append(
                schemas.SourceRegistryEntry(
                    id=document_id,
                    name=name,
                    description=description,
                    url=url,
                )
            )
        span.set_attribute("tool.result_count", len(entries))
        span.set_attribute("tool.total_sources", total)
        return schemas.SourceRegistryListResponse(
            request_id=request.request_id,
            run_id=run_id,
            commit=request.commit,
            sources=entries,
            total=int(total),
        )
