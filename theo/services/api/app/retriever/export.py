"""Helpers for producing export payloads."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
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


def export_search_results(session: Session, request: HybridSearchRequest) -> SearchExportResponse:
    """Run hybrid search and return an export-friendly payload."""

    results = hybrid_search(session, request)
    document_ids = {result.document_id for result in results}

    documents: dict[str, Document] = {}
    if document_ids:
        rows = session.execute(select(Document).where(Document.id.in_(document_ids))).scalars()
        documents = {row.id: row for row in rows}

    export_rows: list[SearchExportRow] = []
    for result in results:
        document = documents.get(result.document_id)
        summary = ExportedDocumentSummary(
            id=result.document_id,
            title=result.document_title if result.document_title is not None else getattr(document, "title", None),
            source_type=getattr(document, "source_type", None),
            collection=getattr(document, "collection", None),
            authors=getattr(document, "authors", None),
            doi=getattr(document, "doi", None),
            venue=getattr(document, "venue", None),
            year=getattr(document, "year", None),
            source_url=getattr(document, "source_url", None),
        )
        passage = PassageSchema.model_validate(result.model_dump())
        export_rows.append(
            SearchExportRow(
                rank=result.rank,
                score=result.score,
                passage=passage,
                document=summary,
            )
        )

    return SearchExportResponse(
        query=request.query,
        osis=request.osis,
        filters=request.filters,
        total_results=len(export_rows),
        results=export_rows,
    )


def export_documents(
    session: Session,
    filters: DocumentExportFilters,
    *,
    include_passages: bool = True,
    limit: int | None = None,
) -> DocumentExportResponse:
    """Return documents (and optionally passages) matching *filters*."""

    query = session.query(Document)
    if filters.collection:
        query = query.filter(Document.collection == filters.collection)
    if filters.source_type:
        query = query.filter(Document.source_type == filters.source_type)
    if filters.author:
        query = query.filter(Document.authors.contains([filters.author]))

    query = query.order_by(Document.created_at.asc())
    if limit is not None:
        documents = query.limit(limit).all()
    else:
        documents = query.all()

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
                provenance_score=document.provenance_score,
                metadata=document.bib_json,
                passages=passages,
            )
        )

    if not include_passages:
        total_passages = 0

    return DocumentExportResponse(
        filters=filters,
        include_passages=include_passages,
        limit=limit,
        total_documents=len(detail_records),
        total_passages=total_passages,
        documents=detail_records,
    )

