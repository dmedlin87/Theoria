"""Routes responsible for citation export bundles."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from ...errors import ExportError, Severity
from ...export.citations import build_citation_export, render_citation_markdown
from ...export.formatters import render_bundle
from ...models.export import CitationExportRequest
from ...models.verses import VerseMentionsFilters
from ...retriever.verses import get_mentions_for_osis
from ...facades.database import get_session
from .utils import _BAD_REQUEST_RESPONSE, fetch_documents_by_ids, finalize_response

router = APIRouter()


def _format_anchor_label(passage: Any) -> str | None:
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


@router.post("/citations", responses=_BAD_REQUEST_RESPONSE)
def export_citation_bundle(
    request: Request,
    payload: CitationExportRequest,
    session: Session = Depends(get_session),
):
    """Return rendered citations for selected documents or verse mentions."""

    normalized_format = payload.format.lower()
    if normalized_format not in {"json", "ndjson", "csv", "markdown"}:
        raise ExportError(
            "Unsupported citation format",
            code="EXPORT_UNSUPPORTED_FORMAT",
            status_code=status.HTTP_400_BAD_REQUEST,
            severity=Severity.USER,
            hint="Use json, ndjson, csv, or markdown when requesting citations.",
        )

    ordered_ids: list[str] = []
    anchor_map: dict[str, list[dict[str, Any]]] = {}

    if payload.document_ids:
        ordered_ids.extend(payload.document_ids)

    if payload.osis:
        filters = payload.filters
        mentions = get_mentions_for_osis(
            session,
            payload.osis,
            VerseMentionsFilters(
                collection=filters.collection,
                source_type=filters.source_type,
                author=filters.author,
            ),
            limit=payload.limit,
        )

        for mention in mentions:
            document_id = mention.passage.document_id
            if document_id not in ordered_ids:
                ordered_ids.append(document_id)
            anchor_map.setdefault(document_id, [])
            label = _format_anchor_label(mention.passage)
            anchor_map[document_id].append(
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

    documents = fetch_documents_by_ids(session, ordered_ids)
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

    extension_map = {
        "json": "json",
        "ndjson": "ndjson",
        "csv": "csv",
        "markdown": "md",
    }
    extension = extension_map[normalized_format]
    gzip_when_text = isinstance(body, str)

    return finalize_response(
        request,
        body,
        media_type=media_type,
        export_type="citations",
        extension=extension,
        gzip_when_text=gzip_when_text,
    )


__all__ = ["router", "export_citation_bundle"]
