"""Routes supporting Zotero citation export."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ...errors import ExportError, Severity
from ...export.citations import CitationSource, build_citation_export
from ...export.zotero import (
    ZoteroExportError,
    export_to_zotero,
)
from ...models.export import ZoteroExportRequest, ZoteroExportResponse
from theo.application.facades.database import get_session as get_db_session
from .utils import _BAD_REQUEST_RESPONSE, fetch_documents_by_ids

router = APIRouter()


@router.post("/zotero", response_model=ZoteroExportResponse, responses=_BAD_REQUEST_RESPONSE)
async def export_to_zotero_endpoint(
    payload: ZoteroExportRequest,
    session: Session = Depends(get_db_session),
) -> ZoteroExportResponse:
    """Export selected documents to a Zotero library."""

    if not payload.user_id and not payload.group_id:
        raise ExportError(
            "Either user_id or group_id must be provided",
            code="EXPORT_MISSING_ZOTERO_TARGET",
            status_code=status.HTTP_400_BAD_REQUEST,
            severity=Severity.USER,
            hint="Specify your Zotero user ID for personal library or group ID for group library.",
        )

    if not payload.document_ids:
        raise ExportError(
            "No documents selected for export",
            code="EXPORT_NO_DOCUMENTS",
            status_code=status.HTTP_400_BAD_REQUEST,
            severity=Severity.USER,
            hint="Select at least one document to export to Zotero.",
        )

    documents = fetch_documents_by_ids(session, payload.document_ids)

    _, records, csl_entries = build_citation_export(
        documents,
        style="csl-json",
        anchors=None,
        filters={},
        export_id=None,
    )

    sources: list[CitationSource] = [CitationSource.from_object(doc) for doc in documents]

    try:
        result = await export_to_zotero(
            sources=sources,
            csl_entries=csl_entries,
            api_key=payload.api_key,
            user_id=payload.user_id,
            group_id=payload.group_id,
        )
        return ZoteroExportResponse(**result)
    except ZoteroExportError as exc:
        raise ExportError(
            str(exc),
            code="EXPORT_ZOTERO_FAILED",
            status_code=status.HTTP_400_BAD_REQUEST,
            severity=Severity.USER,
            hint="Check your Zotero API key and library ID, then try again.",
        ) from exc


__all__ = ["router", "export_to_zotero_endpoint", "export_to_zotero"]
