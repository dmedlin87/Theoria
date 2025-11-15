"""Shared helpers for export route modules."""

from __future__ import annotations

import gzip
from collections.abc import Sequence
from datetime import UTC, datetime

from fastapi import Request, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from theo.application.facades import database  # noqa: F401

from ...errors import ExportError, Severity
from ...export.formatters import DEFAULT_FILENAME_PREFIX
from ...persistence_models import Document

_BAD_REQUEST_RESPONSE = {
    status.HTTP_400_BAD_REQUEST: {"description": "Invalid request"}
}

_DELIVERABLE_ERROR_RESPONSES = {
    **_BAD_REQUEST_RESPONSE,
    status.HTTP_404_NOT_FOUND: {"description": "Deliverable not found"},
}


def parse_fields(fields: str | None) -> set[str] | None:
    """Return a cleaned set of field selectors from a comma-delimited string."""

    if not fields:
        return None
    parsed = {item.strip() for item in fields.split(",") if item.strip()}
    return parsed or None


def should_gzip(request: Request) -> bool:
    """Return ``True`` when the client accepts gzip encoded responses."""

    header = request.headers.get("accept-encoding", "")
    return "gzip" in header.lower()


def build_filename(export_type: str, extension: str) -> str:
    """Return a timestamped filename for an export payload."""

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{DEFAULT_FILENAME_PREFIX}_{export_type}_{timestamp}.{extension}"


def finalize_response(
    request: Request,
    body: str | bytes,
    *,
    media_type: str,
    export_type: str,
    extension: str,
    gzip_when_text: bool = True,
) -> Response:
    """Create a :class:`Response` with consistent headers for file downloads."""

    is_text = isinstance(body, str)
    payload = body.encode("utf-8") if is_text else body
    headers: dict[str, str] = {}
    filename = build_filename(export_type, extension)

    if gzip_when_text and is_text and should_gzip(request):
        payload = gzip.compress(payload)
        headers["Content-Encoding"] = "gzip"
        filename += ".gz"

    headers["Content-Disposition"] = f"attachment; filename={filename}"
    return Response(content=payload, media_type=media_type, headers=headers)


def fetch_documents_by_ids(
    session: Session, document_ids: Sequence[str]
) -> list[Document]:
    """Return documents for *document_ids* preserving the input order."""

    if not document_ids:
        raise ExportError(
            "No documents matched the request",
            code="EXPORT_NO_DOCUMENTS",
            status_code=status.HTTP_404_NOT_FOUND,
            severity=Severity.USER,
            hint="Adjust filters so at least one document is selected.",
        )

    rows = session.execute(
        select(Document)
        .options(selectinload(Document.passages))
        .where(Document.id.in_(document_ids))
    ).scalars()
    document_index = {row.id: row for row in rows}
    missing = [doc_id for doc_id in document_ids if doc_id not in document_index]

    if missing:
        raise ExportError(
            f"Unknown document(s): {', '.join(sorted(missing))}",
            code="EXPORT_UNKNOWN_DOCUMENT",
            status_code=status.HTTP_404_NOT_FOUND,
            severity=Severity.USER,
            hint="Confirm the requested documents exist before exporting.",
        )

    return [document_index[doc_id] for doc_id in document_ids]


__all__ = [
    "DEFAULT_FILENAME_PREFIX",
    "_BAD_REQUEST_RESPONSE",
    "_DELIVERABLE_ERROR_RESPONSES",
    "build_filename",
    "fetch_documents_by_ids",
    "finalize_response",
    "parse_fields",
    "should_gzip",
]
