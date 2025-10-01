# ruff: noqa: E402
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.export.formatters import build_document_export
from theo.services.api.app.models.base import Passage
from theo.services.api.app.models.documents import DocumentDetailResponse
from theo.services.api.app.models.export import (
    DocumentExportFilters,
    DocumentExportResponse,
)


def _build_document_with_passage(text: str) -> DocumentDetailResponse:
    now = datetime.now(timezone.utc)
    return DocumentDetailResponse(
        id="doc-1",
        title="Example",
        source_type="markdown",
        collection="sermons",
        authors=["Jane"],
        doi=None,
        venue=None,
        year=None,
        created_at=now,
        updated_at=now,
        provenance_score=None,
        source_url=None,
        channel=None,
        video_id=None,
        duration_seconds=None,
        storage_path=None,
        abstract=None,
        topics=None,
        enrichment_version=None,
        primary_topic=None,
        metadata=None,
        passages=[
            Passage(
                id="passage-1",
                document_id="doc-1",
                text=text,
            )
        ],
    )


def _build_document_export(document: DocumentDetailResponse) -> DocumentExportResponse:
    return DocumentExportResponse(
        filters=DocumentExportFilters(),
        include_passages=True,
        limit=None,
        cursor=None,
        next_cursor=None,
        total_documents=1,
        total_passages=1,
        documents=[document],
    )


def test_repro_document_export_passage_text_field() -> None:
    """Including passages.text in fields should return text even if include_text is False."""

    document = _build_document_with_passage("Example passage")
    response = _build_document_export(document)

    _, records = build_document_export(
        response,
        include_passages=True,
        include_text=False,
        fields={"passages.text"},
    )

    assert records == [
        {"passages": [{"text": "Example passage"}]}
    ]
