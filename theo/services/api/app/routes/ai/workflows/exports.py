"""Export-related workflow routes."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from theo.services.api.app.ai import (
    build_sermon_deliverable,
    build_transcript_deliverable,
    generate_sermon_prep_outline,
)
from theo.services.api.app.ai.rag import GuardrailError, RAGCitation
from theo.application.facades.database import get_session
from theo.services.api.app.db.models import Document, Passage
from theo.services.api.app.export import citations as citation_exports
from theo.services.api.app.export.citations import build_citation_export
from theo.services.api.app.models.ai import (
    CitationExportRequest,
    CitationExportResponse,
    ExportDeliverableResponse,
    ExportPresetId,
    SermonPrepRequest,
    TranscriptExportRequest,
)
from theo.services.api.app.models.base import Passage as PassageSchema
from theo.services.api.app.models.documents import DocumentDetailResponse
from theo.services.api.app.models.export import serialise_asset_content
from .guardrails import guardrail_http_exception

router = APIRouter()


# NOTE:
# ``tests/api/test_ai_citation_export.py`` imports ``_CSL_TYPE_MAP`` and
# ``_build_csl_entry`` from this module.  Historically these helpers lived here
# and the test suite (and potentially downstream code) still relies on that
# public contract.  A recent refactor moved the implementation into
# ``theo.services.api.app.export.citations`` but forgot to keep the re-export in
# place, breaking import at test collection time.  Restoring the thin wrapper
# keeps the more robust shared implementation while maintaining the old import
# path.
_CSL_TYPE_MAP: dict[str, str] = {
    "sermon": citation_exports._infer_csl_type("sermon"),
    "video": citation_exports._infer_csl_type("video"),
    "web": citation_exports._infer_csl_type("web"),
}


def _build_csl_entry(
    record: Mapping[str, Any], citations: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Return a CSL entry for the provided *record*.

    The heavy lifting lives in :mod:`theo.services.api.app.export.citations`.
    This wrapper only exists to preserve the historical public API of this
    module, delegating to the shared implementation for the actual conversion.
    """

    source = citation_exports.CitationSource.from_object(record)
    return citation_exports._build_csl_entry(source, citations)


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
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid request"},
        status.HTTP_404_NOT_FOUND: {"description": "Resource not found"},
    },
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
    for doc_id in document_order:
        document = document_index[doc_id]
        doc_citations = citation_map[doc_id]
        detail = _build_document_detail(document, doc_citations, passage_index)
        document_details.append(detail)

    anchor_map: dict[str, list[dict[str, Any]]] = {}
    for document_id, citations in citation_map.items():
        entries: list[dict[str, Any]] = []
        for citation in citations:
            entries.append(
                {
                    "osis": citation.osis,
                    "label": citation.anchor,
                    "snippet": citation.snippet,
                    "passage_id": citation.passage_id,
                }
            )
        anchor_map[document_id] = entries

    manifest, citation_records, csl_entries = build_citation_export(
        document_details,
        style="csl-json",
        anchors=anchor_map,
        filters={},
    )
    manifest = manifest.model_copy(update={"type": "documents"})

    def _strip_doi_prefix(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        if not cleaned:
            return None
        lowered = cleaned.lower()
        prefixes = (
            "https://doi.org/",
            "http://doi.org/",
            "https://dx.doi.org/",
            "http://dx.doi.org/",
            "doi.org/",
        )
        for prefix in prefixes:
            if lowered.startswith(prefix):
                return cleaned[len(prefix) :].strip() or None
        if lowered.startswith("doi:"):
            return cleaned[4:].strip() or None
        return cleaned

    detail_index = {detail.id: detail for detail in document_details}
    record_dicts: list[dict[str, Any]] = []
    for record in citation_records:
        record_dict = dict(record)
        document_id = record_dict.get("document_id")
        detail = detail_index.get(document_id) if document_id else None
        if detail:
            passages = [
                passage.model_dump(by_alias=True)
                for passage in detail.passages
            ]
            if passages:
                record_dict["passages"] = passages
        doi_value = record_dict.get("doi")
        if doi_value is not None:
            record_dict["doi"] = _strip_doi_prefix(doi_value)
        record_dicts.append(record_dict)

    for entry in csl_entries:
        doi_value = entry.get("DOI")
        if doi_value is not None:
            stripped = _strip_doi_prefix(doi_value)
            if stripped:
                entry["DOI"] = stripped
            else:
                entry.pop("DOI", None)

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


__all__ = [
    "_CSL_TYPE_MAP",
    "_build_csl_entry",
    "router",
    "export_citations",
    "sermon_prep_export",
    "transcript_export",
]
