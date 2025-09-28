"""Export endpoints."""

from __future__ import annotations

import gzip
from datetime import UTC, datetime

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..ai.rag import (
    GuardrailError,
    build_sermon_deliverable,
    build_transcript_deliverable,
    generate_sermon_prep_outline,
)
from ..core.database import get_session
from ..export.formatters import (
    DEFAULT_FILENAME_PREFIX,
    build_document_export,
    build_search_export,
    render_bundle,
)
from ..models.export import (
    DeliverableRequest,
    DeliverableResponse,
    DocumentExportFilters,
)
from ..models.search import HybridSearchFilters, HybridSearchRequest
from ..retriever.export import export_documents, export_search_results

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


def _normalise_formats(formats: Sequence[str] | None) -> list[str]:
    if not formats:
        return ["markdown"]
    return [fmt.lower() for fmt in formats]


@router.post(
    "/deliverable",
    response_model=DeliverableResponse,
    responses=_DELIVERABLE_ERROR_RESPONSES,
)
def export_deliverable(
    payload: DeliverableRequest,
    session: Session = Depends(get_session),
) -> DeliverableResponse:
    """Generate sermon or transcript deliverables under a unified schema."""

    formats = _normalise_formats(payload.formats)
    try:
        if payload.type == "sermon":
            if not payload.topic:
                raise HTTPException(
                    status_code=400,
                    detail="topic is required for sermon deliverables",
                )
            response = generate_sermon_prep_outline(
                session,
                topic=payload.topic,
                osis=payload.osis,
                filters=payload.filters,
                model_name=payload.model,
            )
            package = build_sermon_deliverable(
                response,
                formats=formats,
                filters=payload.filters.model_dump(exclude_none=True),
            )
        elif payload.type == "transcript":
            if not payload.document_id:
                raise HTTPException(
                    status_code=400,
                    detail="document_id is required for transcript deliverables",
                )
            package = build_transcript_deliverable(
                session,
                payload.document_id,
                formats=formats,
            )
        else:  # pragma: no cover - payload validation guards this
            raise HTTPException(status_code=400, detail="Unsupported deliverable type")
    except GuardrailError as exc:
        status_code = 422 if payload.type == "sermon" else 404
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DeliverableResponse(
        export_id=package.manifest.export_id,
        status="completed",
        manifest=package.manifest,
        assets=package.assets,
        message=f"Generated {payload.type} deliverable",
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
