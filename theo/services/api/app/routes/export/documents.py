"""Routes for exporting document collections."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from ...errors import ExportError, Severity
from ...export.formatters import build_document_export, render_bundle
from ...models.export import DocumentExportFilters
from ...retriever.export import export_documents
from ...facades.database import get_session
from .utils import _BAD_REQUEST_RESPONSE, finalize_response, parse_fields

router = APIRouter()


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
        description="Response format (json, ndjson, html, obsidian, or pdf).",
    ),
    session: Session = Depends(get_session),
):
    """Return documents and their passages for offline processing."""

    normalized_format = output_format.lower()
    allowed_formats = {"json", "ndjson", "html", "pdf", "obsidian"}
    if normalized_format not in allowed_formats:
        raise ExportError(
            "Unsupported format for document export",
            code="EXPORT_UNSUPPORTED_FORMAT",
            status_code=status.HTTP_400_BAD_REQUEST,
            severity=Severity.USER,
            hint="Choose json, ndjson, html, obsidian, or pdf when exporting documents.",
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
        fields=parse_fields(fields),
    )

    try:
        body, media_type = render_bundle(
            manifest,
            records,
            output_format=normalized_format,
        )
    except ValueError as exc:  # pragma: no cover - validated earlier
        raise ExportError(
            str(exc),
            code="EXPORT_RENDER_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            severity=Severity.USER,
            hint="Adjust export parameters to render the requested format.",
        ) from exc

    extension_map = {
        "obsidian": "md",
        "html": "html",
        "pdf": "pdf",
        "ndjson": "ndjson",
        "json": "json",
    }
    extension = extension_map.get(normalized_format, normalized_format)

    return finalize_response(
        request,
        body,
        media_type=media_type,
        export_type="documents",
        extension=extension,
        gzip_when_text=isinstance(body, str),
    )


__all__ = ["router", "export_documents_endpoint"]
