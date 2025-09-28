"""Helpers for producing export payloads."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..db.models import Document, Passage
from ..models.base import Passage as PassageSchema
from ..models.documents import DocumentDetailResponse
from ..models.export import (
    DocumentExportFilters,
    DocumentExportResponse,
    ExportedDocumentSummary,
    SearchExportResponse,
    SearchExportRow,
)
from ..models.search import HybridSearchRequest
from ..models.verses import VerseMentionsFilters
from ..retriever.verses import get_mentions_for_osis
from .hybrid import hybrid_search


def _passage_to_schema(passage: Passage) -> PassageSchema:
    """Convert a ``Passage`` ORM instance to a Pydantic schema."""

    return PassageSchema(
        id=passage.id,
        document_id=passage.document_id,
        text=passage.text,
        osis_ref=passage.osis_ref,
        page_no=passage.page_no,
        t_start=passage.t_start,
        t_end=passage.t_end,
        score=None,
        meta=passage.meta,
    )


def _primary_topic(document: Document) -> str | None:
    """Extract the primary topic from document metadata when available."""

    if document.bib_json and isinstance(document.bib_json, dict):
        primary = document.bib_json.get("primary_topic")
        if isinstance(primary, str):
            return primary
    topics = document.topics
    if isinstance(topics, list) and topics:
        first = topics[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict) and "primary" in first:
            value = first["primary"]
            if isinstance(value, str):
                return value
    if isinstance(topics, dict):
        primary = topics.get("primary")
        if isinstance(primary, str):
            return primary
    return None


def export_search_results(
    session: Session, request: HybridSearchRequest
) -> SearchExportResponse:
    """Run hybrid search and return an export-friendly payload."""

    if request.mode == "mentions" and request.osis:
        mentions = get_mentions_for_osis(
            session,
            request.osis,
            VerseMentionsFilters(
                source_type=request.filters.source_type,
                collection=request.filters.collection,
                author=request.filters.author,
            ),
        )
        return _mentions_to_export_response(mentions, request)

    results = hybrid_search(session, request)
    document_ids = {result.document_id for result in results}

    documents: dict[str, Document] = {}
    if document_ids:
        rows = session.execute(
            select(Document).where(Document.id.in_(document_ids))
        ).scalars()
        documents = {row.id: row for row in rows}

    all_rows: list[SearchExportRow] = []
    after_cursor: list[SearchExportRow] = []
    cursor_found = request.cursor is None
    limit = request.limit or request.k
    for result in results:
        document = documents.get(result.document_id)
        summary = ExportedDocumentSummary(
            id=result.document_id,
            title=result.document_title or getattr(document, "title", None),
            source_type=getattr(document, "source_type", None),
            collection=getattr(document, "collection", None),
            authors=getattr(document, "authors", None),
            doi=getattr(document, "doi", None),
            venue=getattr(document, "venue", None),
            year=getattr(document, "year", None),
            source_url=getattr(document, "source_url", None),
            topics=getattr(document, "topics", None),
            primary_topic=_primary_topic(document) if document else None,
            enrichment_version=getattr(document, "enrichment_version", None),
            provenance_score=getattr(document, "provenance_score", None),
        )
        passage = PassageSchema.model_validate(result.model_dump())
        row = SearchExportRow(
            rank=result.rank,
            score=result.score,
            passage=passage,
            document=summary,
            snippet=getattr(result, "snippet", None),
        )
        all_rows.append(row)
        if not cursor_found:
            if result.id == request.cursor:
                cursor_found = True
            continue
        if cursor_found:
            after_cursor.append(row)

    if request.cursor and not cursor_found:
        after_cursor = all_rows

    returned_rows = after_cursor[:limit]
    next_cursor = None
    if after_cursor and len(after_cursor) > len(returned_rows):
        next_cursor = returned_rows[-1].passage.id if returned_rows else None

    return SearchExportResponse(
        query=request.query,
        osis=request.osis,
        filters=request.filters,
        mode=request.mode,
        cursor=request.cursor,
        limit=limit,
        next_cursor=next_cursor,
        total_results=len(after_cursor),
        results=returned_rows,
    )


def export_documents(
    session: Session,
    filters: DocumentExportFilters,
    *,
    include_passages: bool = True,
    limit: int | None = None,
    cursor: str | None = None,
) -> DocumentExportResponse:
    """Return documents (and optionally passages) matching *filters*."""

    query = session.query(Document)
    if filters.collection:
        query = query.filter(Document.collection == filters.collection)
    if filters.source_type:
        query = query.filter(Document.source_type == filters.source_type)
    if filters.author:
        query = query.filter(Document.authors.contains([filters.author]))

    if cursor:
        anchor = session.get(Document, cursor)
        if anchor:
            query = query.filter(
                or_(
                    Document.created_at > anchor.created_at,
                    and_(
                        Document.created_at == anchor.created_at,
                        Document.id > anchor.id,
                    ),
                )
            )

    query = query.order_by(Document.created_at.asc(), Document.id.asc())
    fetch_limit = limit + 1 if limit is not None else None
    if limit is not None:
        documents = query.limit(fetch_limit).all()
    else:
        documents = query.all()

    has_more = False
    if limit is not None and len(documents) > limit:
        has_more = True
        documents = documents[:limit]

    passage_map: dict[str, list[PassageSchema]] = defaultdict(list)
    total_passages = 0
    if include_passages and documents:
        doc_ids = [doc.id for doc in documents]
        rows = (
            session.query(Passage)
            .filter(Passage.document_id.in_(doc_ids))
            .order_by(
                Passage.document_id.asc(),
                Passage.page_no.asc(),
                Passage.t_start.asc(),
                Passage.start_char.asc(),
            )
            .all()
        )
        for passage in rows:
            passage_map[passage.document_id].append(_passage_to_schema(passage))
        total_passages = sum(len(items) for items in passage_map.values())

    detail_records: list[DocumentDetailResponse] = []
    for document in documents:
        passages = passage_map[document.id] if include_passages else []
        detail_records.append(
            DocumentDetailResponse(
                id=document.id,
                title=document.title,
                source_type=document.source_type,
                collection=document.collection,
                authors=document.authors,
                doi=document.doi,
                venue=document.venue,
                year=document.year,
                created_at=document.created_at,
                updated_at=document.updated_at,
                source_url=document.source_url,
                channel=document.channel,
                video_id=document.video_id,
                duration_seconds=document.duration_seconds,
                storage_path=document.storage_path,
                abstract=document.abstract,
                topics=document.topics,
                enrichment_version=document.enrichment_version,
                primary_topic=_primary_topic(document),
                provenance_score=document.provenance_score,
                meta=document.bib_json,
                passages=passages,
            )
        )
    next_cursor = documents[-1].id if documents and has_more else None
    return DocumentExportResponse(
        filters=filters,
        include_passages=include_passages,
        limit=limit,
        cursor=cursor,
        next_cursor=next_cursor,
        total_documents=len(detail_records),
        total_passages=total_passages,
        documents=detail_records,
    )


def _mentions_to_export_response(
    mentions, request: HybridSearchRequest
) -> SearchExportResponse:
    """Convert verse mentions into a search export payload."""

    limit = request.limit or request.k
    cursor_found = request.cursor is None
    after_cursor: list[SearchExportRow] = []

    for idx, mention in enumerate(mentions, start=1):
        passage = mention.passage
        summary = ExportedDocumentSummary(
            id=passage.document_id,
            title=passage.meta.get("document_title") if passage.meta else None,
            source_type=passage.meta.get("source_type") if passage.meta else None,
            collection=passage.meta.get("collection") if passage.meta else None,
            authors=passage.meta.get("authors") if passage.meta else None,
            doi=passage.meta.get("doi") if passage.meta else None,
            venue=passage.meta.get("venue") if passage.meta else None,
            year=passage.meta.get("year") if passage.meta else None,
            source_url=passage.meta.get("source_url") if passage.meta else None,
            topics=passage.meta.get("topics") if passage.meta else None,
            primary_topic=passage.meta.get("primary_topic") if passage.meta else None,
            enrichment_version=(
                passage.meta.get("enrichment_version") if passage.meta else None
            ),
            provenance_score=(
                passage.meta.get("provenance_score") if passage.meta else None
            ),
        )
        row = SearchExportRow(
            rank=idx,
            score=None,
            passage=passage,
            document=summary,
            snippet=mention.context_snippet,
        )
        if not cursor_found and passage.id == request.cursor:
            cursor_found = True
            continue
        if cursor_found:
            after_cursor.append(row)

    returned_rows = after_cursor[:limit]
    next_cursor = None
    if after_cursor and len(after_cursor) > len(returned_rows):
        next_cursor = returned_rows[-1].passage.id if returned_rows else None

    return SearchExportResponse(
        query=request.query,
        osis=request.osis,
        filters=request.filters,
        mode=request.mode,
        cursor=request.cursor,
        limit=limit,
        next_cursor=next_cursor,
        total_results=len(after_cursor),
        results=returned_rows,
    )
