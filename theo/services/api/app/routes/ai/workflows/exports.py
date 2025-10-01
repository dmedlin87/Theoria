"""Citation and deliverable export routes."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ....ai import build_sermon_deliverable, build_transcript_deliverable, generate_sermon_prep_outline
from ....ai.rag import GuardrailError, RAGCitation
from ....core.database import get_session
from ....db.models import Document, Passage
from ....export.formatters import build_document_export
from ....models.ai import (
    CitationExportRequest,
    CitationExportResponse,
    ExportDeliverableResponse,
    ExportPresetId,
    SermonPrepRequest,
    TranscriptExportRequest,
)
from ....models.base import Passage as PassageSchema
from ....models.documents import DocumentDetailResponse
from ....models.export import (
    DocumentExportFilters,
    DocumentExportResponse,
    serialise_asset_content,
)

from .common import BAD_REQUEST_NOT_FOUND_RESPONSES
from .guardrails import guardrail_http_exception

router = APIRouter()

__all__ = ["router"]


def _extract_primary_topic(document: Document) -> str | None:
    """Return the primary topic for *document* when available."""

    if document.bib_json and isinstance(document.bib_json, dict):
        primary = document.bib_json.get("primary_topic")
        if isinstance(primary, str):
            return primary
    topics = document.topics
    if isinstance(topics, list) and topics:
        first = topics[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            value = first.get("primary")
            if isinstance(value, str):
                return value
    if isinstance(topics, dict):
        primary = topics.get("primary")
        if isinstance(primary, str):
            return primary
    return None


def _normalise_author(name: str) -> dict[str, str]:
    parts = [segment.strip() for segment in name.replace("  ", " ").split()] if name else []
    if "," in name:
        family, given = [segment.strip() for segment in name.split(",", 1)]
        if family and given:
            return {"given": given, "family": family}
    if len(parts) >= 2:
        return {"given": " ".join(parts[:-1]), "family": parts[-1]}
    return {"literal": name}


_CSL_TYPE_MAP = {
    "article": "article-journal",
    "journal": "article-journal",
    "book": "book",
    "video": "motion_picture",
    "audio": "song",
    "sermon": "speech",
    "web": "webpage",
}


def _infer_csl_type(source_type: str | None) -> str:
    if not source_type:
        return "article-journal"
    normalized = source_type.lower()
    for key, value in _CSL_TYPE_MAP.items():
        if key in normalized:
            return value
    return "article-journal"


def _build_csl_entry(
    record: Mapping[str, Any], citations: Sequence[RAGCitation]
) -> dict[str, Any]:
    authors: list[dict[str, str]] = []
    for name in record.get("authors") or []:
        if isinstance(name, str) and name.strip():
            authors.append(_normalise_author(name.strip()))

    entry: dict[str, Any] = {
        "id": record.get("document_id"),
        "type": _infer_csl_type(record.get("source_type")),
        "title": record.get("title"),
    }
    if authors:
        entry["author"] = authors
    year = record.get("year")
    if isinstance(year, int):
        entry["issued"] = {"date-parts": [[year]]}
    doi = record.get("doi")
    if isinstance(doi, str) and doi:
        entry["DOI"] = doi
    url = record.get("source_url")
    if isinstance(url, str) and url:
        entry["URL"] = url
    venue = record.get("venue")
    if isinstance(venue, str) and venue:
        entry["container-title"] = venue
    collection = record.get("collection")
    if isinstance(collection, str) and collection:
        entry["collection-title"] = collection
    abstract = record.get("abstract")
    if isinstance(abstract, str) and abstract:
        entry["abstract"] = abstract

    anchor_entries = []
    for citation in citations:
        anchor_label = f"{citation.osis} ({citation.anchor})" if citation.anchor else citation.osis
        anchor_entries.append(anchor_label)
    if anchor_entries:
        entry["note"] = "Anchors: " + "; ".join(anchor_entries)

    return entry


def _build_document_detail(
    document: Document,
    citations: Sequence[RAGCitation],
    passage_index: Mapping[str, Passage],
) -> DocumentDetailResponse:
    passages: list[PassageSchema] = []
    for citation in citations:
        passage = passage_index.get(citation.passage_id) if citation.passage_id else None
        if passage:
            meta = dict(passage.meta or {})
            meta.setdefault("anchor", citation.anchor)
            meta.setdefault("snippet", citation.snippet)
            passages.append(
                PassageSchema(
                    id=passage.id,
                    document_id=passage.document_id,
                    text=passage.text,
                    osis_ref=passage.osis_ref or citation.osis,
                    page_no=passage.page_no,
                    t_start=passage.t_start,
                    t_end=passage.t_end,
                    score=None,
                    meta=meta,
                )
            )
        else:
            passages.append(
                PassageSchema(
                    id=citation.passage_id or f"{citation.document_id}:{citation.index}",
                    document_id=citation.document_id,
                    text=citation.snippet,
                    osis_ref=citation.osis,
                    page_no=None,
                    t_start=None,
                    t_end=None,
                    score=None,
                    meta={"anchor": citation.anchor, "snippet": citation.snippet},
                )
            )

    title = document.title or (citations[0].document_title if citations else None)

    source_url = document.source_url
    for citation in citations:
        fields_set = getattr(citation, "model_fields_set", set())
        if "source_url" in fields_set:
            source_url = citation.source_url
            break

    return DocumentDetailResponse(
        id=document.id,
        title=title,
        source_type=document.source_type,
        collection=document.collection,
        authors=document.authors,
        doi=document.doi,
        venue=document.venue,
        year=document.year,
        created_at=document.created_at,
        updated_at=document.updated_at,
        source_url=source_url,
        channel=document.channel,
        video_id=document.video_id,
        duration_seconds=document.duration_seconds,
        storage_path=document.storage_path,
        abstract=document.abstract,
        topics=document.topics,
        enrichment_version=document.enrichment_version,
        primary_topic=_extract_primary_topic(document),
        provenance_score=document.provenance_score,
        meta=document.bib_json,
        passages=passages,
    )


@router.post(
    "/citations/export",
    response_model=CitationExportResponse,
    responses=BAD_REQUEST_NOT_FOUND_RESPONSES,
)
def export_citations(
    payload: CitationExportRequest, session: Session = Depends(get_session)
) -> CitationExportResponse:
    """Return CSL-JSON and manager payloads for the supplied citations."""

    if not payload.citations:
        raise HTTPException(status_code=400, detail="citations cannot be empty")

    ordered_citations = sorted(payload.citations, key=lambda citation: citation.index)
    citation_map: dict[str, list[RAGCitation]] = {}
    document_order: list[str] = []
    for citation in ordered_citations:
        document_id = citation.document_id
        if not document_id:
            raise HTTPException(
                status_code=400, detail="citations must include a document_id"
            )
        bucket = citation_map.setdefault(document_id, [])
        bucket.append(citation)
        if document_id not in document_order:
            document_order.append(document_id)

    document_ids = list(citation_map.keys())
    rows = session.execute(
        select(Document).where(Document.id.in_(document_ids))
    ).scalars()
    document_index = {row.id: row for row in rows}
    missing_documents = [doc_id for doc_id in document_ids if doc_id not in document_index]
    if missing_documents:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown document(s): {', '.join(sorted(missing_documents))}",
        )

    passage_ids = {
        citation.passage_id
        for citation in ordered_citations
        if citation.passage_id is not None
    }
    passage_index: dict[str, Passage] = {}
    if passage_ids:
        passage_rows = session.execute(
            select(Passage).where(Passage.id.in_(passage_ids))
        ).scalars()
        passage_index = {row.id: row for row in passage_rows}

    document_details: list[DocumentDetailResponse] = []
    total_passages = 0
    for document_id in document_order:
        document = document_index[document_id]
        doc_citations = citation_map[document_id]
        detail = _build_document_detail(document, doc_citations, passage_index)
        total_passages += len(detail.passages)
        document_details.append(detail)

    export_payload = DocumentExportResponse(
        filters=DocumentExportFilters(),
        include_passages=True,
        limit=None,
        cursor=None,
        next_cursor=None,
        total_documents=len(document_details),
        total_passages=total_passages,
        documents=document_details,
    )
    manifest, records = build_document_export(
        export_payload,
        include_passages=True,
        include_text=False,
        fields=None,
        export_id=None,
    )
    record_dicts = [dict(record) for record in records]
    csl_entries: list[dict[str, Any]] = []
    for record in record_dicts:
        raw_document_id = record.get("document_id")
        citations = (
            citation_map.get(raw_document_id, [])
            if isinstance(raw_document_id, str)
            else []
        )
        csl_entries.append(_build_csl_entry(record, citations))
    manager_payload = {
        "format": "csl-json",
        "export_id": manifest.export_id,
        "zotero": {"items": csl_entries},
        "mendeley": {"documents": csl_entries},
    }

    return CitationExportResponse(
        manifest=manifest,
        records=record_dicts,
        csl=csl_entries,
        manager_payload=manager_payload,
    )


@router.post("/sermon-prep/export", response_model=ExportDeliverableResponse)
def sermon_prep_export(
    payload: SermonPrepRequest,
    format: str = Query(
        default="markdown", description="markdown, ndjson, csv, or pdf"
    ),
    session: Session = Depends(get_session),
) -> ExportDeliverableResponse:
    try:
        response = generate_sermon_prep_outline(
            session,
            topic=payload.topic,
            osis=payload.osis,
            filters=payload.filters,
            model_name=payload.model,
        )
    except GuardrailError as exc:
        return guardrail_http_exception(
            exc,
            session=session,
            question=None,
            osis=payload.osis,
            filters=payload.filters,
        )
    normalized = format.lower()
    package = build_sermon_deliverable(
        response,
        formats=[normalized],
        filters=payload.filters.model_dump(exclude_none=True),
    )
    try:
        preset = _SERMON_PRESET_MAP[normalized]
    except KeyError as exc:
        raise HTTPException(status_code=400, detail="unsupported sermon export format") from exc
    asset = package.get_asset(normalized)
    return ExportDeliverableResponse(
        preset=preset,
        format=asset.format,
        filename=asset.filename,
        media_type=asset.media_type,
        content=serialise_asset_content(asset.content),
    )


@router.post("/transcript/export", response_model=ExportDeliverableResponse)
def transcript_export(
    payload: TranscriptExportRequest,
    session: Session = Depends(get_session),
) -> ExportDeliverableResponse:
    normalized = payload.format.lower()
    try:
        package = build_transcript_deliverable(
            session, payload.document_id, formats=[normalized]
        )
    except GuardrailError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        preset = _TRANSCRIPT_PRESET_MAP[normalized]
    except KeyError as exc:
        raise HTTPException(status_code=400, detail="unsupported transcript export format") from exc
    asset = package.get_asset(normalized)
    return ExportDeliverableResponse(
        preset=preset,
        format=asset.format,
        filename=asset.filename,
        media_type=asset.media_type,
        content=serialise_asset_content(asset.content),
    )


_SERMON_PRESET_MAP: dict[str, ExportPresetId] = {
    "markdown": "sermon-markdown",
    "ndjson": "sermon-ndjson",
    "csv": "sermon-csv",
    "pdf": "sermon-pdf",
}

_TRANSCRIPT_PRESET_MAP: dict[str, ExportPresetId] = {
    "markdown": "transcript-markdown",
    "csv": "transcript-csv",
    "pdf": "transcript-pdf",
}
