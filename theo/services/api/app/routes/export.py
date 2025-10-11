"""Export endpoints."""

from __future__ import annotations

import gzip
from datetime import UTC, datetime

from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..db.models import Document
from ..export.citations import build_citation_export, render_citation_markdown
from ..export.formatters import (
    DEFAULT_FILENAME_PREFIX,
    build_document_export,
    build_search_export,
    generate_export_id,
    render_bundle,
)
from ..models.export import (
    CitationExportRequest,
    DeliverableRequest,
    DeliverableResponse,
    DocumentExportFilters,
)
from ..models.search import HybridSearchFilters, HybridSearchRequest
from ..retriever.export import export_documents, export_search_results
from ..retriever.verses import get_mentions_for_osis
from ..models.verses import VerseMentionsFilters
from ..workers import tasks as worker_tasks

_BAD_REQUEST_RESPONSE = {
    status.HTTP_400_BAD_REQUEST: {"description": "Invalid request"}
}
_DELIVERABLE_ERROR_RESPONSES = {
    **_BAD_REQUEST_RESPONSE,
    status.HTTP_404_NOT_FOUND: {"description": "Deliverable not found"},
}


router = APIRouter()


def _parse_fields(fields: str | None) -> set[str] | None:
    if not fields:
        return None
    parsed = {item.strip() for item in fields.split(",") if item.strip()}
    return parsed or None


def _should_gzip(request: Request) -> bool:
    header = request.headers.get("accept-encoding", "")
    return "gzip" in header.lower()


def _build_filename(export_type: str, extension: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{DEFAULT_FILENAME_PREFIX}_{export_type}_{timestamp}.{extension}"


def _format_anchor_label(passage) -> str | None:
    page_no = getattr(passage, "page_no", None)
    if isinstance(page_no, int):
        return f"p.{page_no}"
    t_start = getattr(passage, "t_start", None)
    t_end = getattr(passage, "t_end", None)
    if isinstance(t_start, (int, float)):
        if isinstance(t_end, (int, float)) and t_end != t_start:
            return f"{int(t_start)}-{int(t_end)}s"
        return f"{int(t_start)}s"
    return None


def _determine_export_id(payload: DeliverableRequest) -> str:
    if payload.type == "transcript" and payload.document_id:
        return f"transcript-{payload.document_id}"
    return generate_export_id()


def _normalise_formats(formats: Sequence[str] | None) -> list[str]:
    if not formats:
        return ["markdown"]
    return [fmt.lower() for fmt in formats]


@router.post("/citations", responses=_BAD_REQUEST_RESPONSE)
def export_citation_bundle(
    request: Request,
    payload: CitationExportRequest,
    session: Session = Depends(get_session),
) -> Response:
    """Return rendered citations for selected documents or verse mentions."""

    normalized_format = payload.format.lower()
    if normalized_format not in {"json", "ndjson", "csv", "markdown"}:
        raise HTTPException(status_code=400, detail="Unsupported citation format")

    if not payload.document_ids and not payload.osis:
        raise HTTPException(
            status_code=400,
            detail="document_ids or osis must be supplied for citation exports",
        )

    ordered_ids: list[str] = []
    seen: set[str] = set()
    if payload.document_ids:
        for candidate in payload.document_ids:
            doc_id = candidate.strip()
            if not doc_id or doc_id in seen:
                continue
            ordered_ids.append(doc_id)
            seen.add(doc_id)

    anchor_map: dict[str, list[dict[str, Any]]] = {}
    if payload.osis:
        verse_filters = VerseMentionsFilters(
            source_type=payload.filters.source_type,
            collection=payload.filters.collection,
            author=payload.filters.author,
        )
        mentions = get_mentions_for_osis(session, payload.osis, verse_filters)
        if payload.limit is not None:
            mentions = mentions[: payload.limit]
        for mention in mentions:
            doc_id = mention.passage.document_id
            if doc_id not in seen:
                ordered_ids.append(doc_id)
                seen.add(doc_id)
            anchors = anchor_map.setdefault(doc_id, [])
            label = _format_anchor_label(mention.passage)
            anchors.append(
                {
                    "osis": mention.passage.osis_ref or payload.osis,
                    "label": label,
                    "snippet": mention.context_snippet,
                    "passage_id": mention.passage.id,
                    "page_no": mention.passage.page_no,
                    "t_start": mention.passage.t_start,
                    "t_end": mention.passage.t_end,
                }
            )

    if not ordered_ids:
        raise HTTPException(status_code=404, detail="No documents matched the request")

    rows = session.execute(
        select(Document).where(Document.id.in_(ordered_ids))
    ).scalars()
    document_index = {row.id: row for row in rows}
    missing = [doc_id for doc_id in ordered_ids if doc_id not in document_index]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown document(s): {', '.join(sorted(missing))}",
        )

    documents = [document_index[doc_id] for doc_id in ordered_ids]
    filter_payload = payload.filters.model_dump(exclude_none=True)
    if payload.osis:
        filter_payload["osis"] = payload.osis

    manifest, records, _ = build_citation_export(
        documents,
        style=payload.style,
        anchors=anchor_map,
        filters=filter_payload,
        export_id=payload.export_id,
    )

    if normalized_format == "markdown":
        body = render_citation_markdown(manifest, records)
        media_type = "text/markdown"
    else:
        body, media_type = render_bundle(
            manifest,
            records,
            output_format=normalized_format,
        )

    body_bytes = body.encode("utf-8")
    filename_extension = {
        "json": "json",
        "ndjson": "ndjson",
        "csv": "csv",
        "markdown": "md",
    }[normalized_format]
    headers: dict[str, str] = {}

    if _should_gzip(request):
        body_bytes = gzip.compress(body_bytes)
        headers["Content-Encoding"] = "gzip"
        filename_extension += ".gz"

    headers["Content-Disposition"] = (
        f"attachment; filename={_build_filename('citations', filename_extension)}"
    )
    return Response(content=body_bytes, media_type=media_type, headers=headers)


@router.post(
    "/deliverable",
    response_model=DeliverableResponse,
    responses=_DELIVERABLE_ERROR_RESPONSES,
)
def export_deliverable(payload: DeliverableRequest) -> DeliverableResponse:
    """Generate sermon or transcript deliverables under a unified schema."""

    formats = _normalise_formats(payload.formats)
    filters = payload.filters.model_dump(exclude_none=True)
    export_id = _determine_export_id(payload)

    try:
        if payload.type == "sermon":
            if not payload.topic:
                raise HTTPException(
                    status_code=400,
                    detail="topic is required for sermon deliverables",
                )
        elif payload.type == "transcript":
            if not payload.document_id:
                raise HTTPException(
                    status_code=400,
                    detail="document_id is required for transcript deliverables",
                )
        else:  # pragma: no cover - payload validation guards this
            raise HTTPException(status_code=400, detail="Unsupported deliverable type")
    except ValueError as exc:  # pragma: no cover - format guard
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        asset_plan = worker_tasks.plan_deliverable_outputs(
            payload.type, formats, export_id
        )
    except ValueError as exc:  # pragma: no cover - guarded above
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    task_kwargs = {
        "export_type": payload.type,
        "formats": formats,
        "export_id": export_id,
        "topic": payload.topic,
        "osis": payload.osis,
        "filters": filters,
        "model": payload.model,
        "document_id": payload.document_id,
    }
    result = worker_tasks.build_deliverable.apply_async(kwargs=task_kwargs)
    job_id = getattr(result, "id", None)

    return DeliverableResponse(
        export_id=export_id,
        status="queued",
        manifest=None,
        manifest_path=f"/exports/{export_id}/manifest.json",
        job_id=job_id,
        assets=asset_plan,
        message=f"Queued {payload.type} deliverable",
    )


@router.get("/search", responses=_BAD_REQUEST_RESPONSE)
def export_search(
    request: Request,
    q: str | None = Query(default=None, description="Keyword query to run."),
    osis: str | None = Query(
        default=None, description="Optional OSIS reference to filter by."
    ),
    collection: str | None = Query(
        default=None, description="Filter results to a collection."
    ),
    author: str | None = Query(default=None, description="Filter by author."),
    source_type: str | None = Query(
        default=None, description="Restrict to a specific source type."
    ),
    k: int = Query(
        default=100, ge=1, le=1000, description="Maximum number of results to export."
    ),
    cursor: str | None = Query(
        default=None, description="Resume from a specific passage identifier."
    ),
    limit: int | None = Query(
        default=None, ge=1, le=1000, description="Maximum number of rows to return."
    ),
    fields: str | None = Query(
        default=None, description="Comma separated list of fields to include."
    ),
    include_text: bool = Query(
        default=False, description="Include full passage text in the export."
    ),
    mode: str = Query(default="results", description="results or mentions."),
    output_format: str = Query(
        default="ndjson",
        alias="format",
        description="Response format (json, ndjson, csv).",
    ),
    session: Session = Depends(get_session),
) -> Response:
    """Return export payload for hybrid search results or verse mentions."""

    normalized_format = output_format.lower()
    if normalized_format not in {"json", "ndjson", "csv"}:
        raise HTTPException(status_code=400, detail="Unsupported format")
    if mode == "mentions" and not osis:
        raise HTTPException(
            status_code=400, detail="mode=mentions requires an osis parameter"
        )
    field_set = _parse_fields(fields)
    limit_value = limit or k
    fetch_k = limit_value + 1 if limit_value is not None else k
    search_request = HybridSearchRequest(
        query=q,
        osis=osis,
        k=max(k, fetch_k),
        limit=limit_value,
        cursor=cursor,
        mode=mode,
        filters=HybridSearchFilters(
            collection=collection, author=author, source_type=source_type
        ),
    )
    response_payload = export_search_results(session, search_request)
    manifest, records = build_search_export(
        response_payload,
        include_text=include_text,
        fields=field_set,
    )

    try:
        body, media_type = render_bundle(
            manifest,
            records,
            output_format=normalized_format,
        )
    except ValueError as exc:  # pragma: no cover - validated earlier
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    body_bytes = body.encode("utf-8")
    filename_extension = normalized_format
    headers: dict[str, str] = {}
    if normalized_format == "ndjson":
        filename_extension = "ndjson"
    elif normalized_format == "csv":
        filename_extension = "csv"
    elif normalized_format == "json":
        filename_extension = "json"

    if _should_gzip(request):
        body_bytes = gzip.compress(body_bytes)
        headers["Content-Encoding"] = "gzip"
        filename_extension += ".gz"

    headers["Content-Disposition"] = (
        f"attachment; filename={_build_filename('search', filename_extension)}"
    )
    return Response(content=body_bytes, media_type=media_type, headers=headers)


@router.get("/documents", responses=_BAD_REQUEST_RESPONSE)
def export_documents_endpoint(
    request: Request,
    collection: str | None = Query(default=None, description="Collection to export."),
    author: str | None = Query(default=None, description="Filter documents by author."),
    source_type: str | None = Query(
        default=None, description="Restrict to a source type."
    ),
    include_passages: bool = Query(
        default=True, description="Whether to include passages in the export."
    ),
    include_text: bool = Query(
        default=False, description="Include passage text when exporting passages."
    ),
    cursor: str | None = Query(
        default=None, description="Resume from a specific document identifier."
    ),
    limit: int | None = Query(
        default=None,
        ge=1,
        le=1000,
        description="Maximum number of documents to export.",
    ),
    fields: str | None = Query(
        default=None, description="Comma separated list of document fields to include."
    ),
    output_format: str = Query(
        default="ndjson",
        alias="format",
        description="Response format (json or ndjson).",
    ),
    session: Session = Depends(get_session),
) -> Response:
    """Return documents and their passages for offline processing."""

    normalized_format = output_format.lower()
    if normalized_format not in {"json", "ndjson"}:
        raise HTTPException(
            status_code=400, detail="Unsupported format for document export"
        )

    filters = DocumentExportFilters(
        collection=collection, author=author, source_type=source_type
    )
    response_payload = export_documents(
        session,
        filters,
        include_passages=include_passages,
        limit=limit,
        cursor=cursor,
    )
    manifest, records = build_document_export(
        response_payload,
        include_passages=include_passages,
        include_text=include_text,
        fields=_parse_fields(fields),
    )

    try:
        body, media_type = render_bundle(
            manifest,
            records,
            output_format=normalized_format,
        )
    except ValueError as exc:  # pragma: no cover - validated earlier
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    body_bytes = body.encode("utf-8")
    filename_extension = normalized_format
    headers: dict[str, str] = {}

    if _should_gzip(request):
        body_bytes = gzip.compress(body_bytes)
        headers["Content-Encoding"] = "gzip"
        filename_extension += ".gz"

    headers["Content-Disposition"] = (
        f"attachment; filename={_build_filename('documents', filename_extension)}"
    )
    return Response(content=body_bytes, media_type=media_type, headers=headers)
