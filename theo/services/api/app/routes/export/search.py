"""Routes powering search export functionality."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from ...errors import ExportError, Severity
from ...export.formatters import build_search_export, render_bundle
from ...models.search import HybridSearchFilters, HybridSearchRequest
from ...retriever.export import export_search_results
from ...facades.database import get_session
from .utils import _BAD_REQUEST_RESPONSE, finalize_response, parse_fields

router = APIRouter()


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
        description="Response format (json, ndjson, csv, html, obsidian, or pdf).",
    ),
    session: Session = Depends(get_session),
):
    """Return export payload for hybrid search results or verse mentions."""

    normalized_format = output_format.lower()
    allowed_formats = {"json", "ndjson", "csv", "html", "pdf", "obsidian"}
    if normalized_format not in allowed_formats:
        raise ExportError(
            "Unsupported format",
            code="EXPORT_UNSUPPORTED_FORMAT",
            status_code=status.HTTP_400_BAD_REQUEST,
            severity=Severity.USER,
            hint="Choose json, ndjson, csv, html, obsidian, or pdf for search exports.",
        )
    if mode == "mentions" and not osis:
        raise ExportError(
            "mode=mentions requires an osis parameter",
            code="EXPORT_MISSING_OSIS",
            status_code=status.HTTP_400_BAD_REQUEST,
            severity=Severity.USER,
            hint="Provide an OSIS reference when exporting verse mentions.",
        )
    field_set = parse_fields(fields)
    limit_value = limit if limit is not None else k
    if limit is not None:
        fetch_k = min(k, limit + 1)
    else:
        fetch_k = k + 1

    search_request = HybridSearchRequest(
        query=q,
        osis=osis,
        k=fetch_k,
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
        "csv": "csv",
        "ndjson": "ndjson",
        "json": "json",
    }
    extension = extension_map.get(normalized_format, normalized_format)

    return finalize_response(
        request,
        body,
        media_type=media_type,
        export_type="search",
        extension=extension,
        gzip_when_text=isinstance(body, str),
    )


__all__ = ["router", "export_search"]
