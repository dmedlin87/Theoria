"""Tests for export formatters."""

from __future__ import annotations

from datetime import UTC, datetime

from theo.services.api.app.export.formatters import build_document_export
from theo.services.api.app.models.documents import DocumentDetailResponse
from theo.services.api.app.models.export import DocumentExportFilters, DocumentExportResponse


def _make_document(metadata: dict[str, object]) -> DocumentDetailResponse:
    """Return a ``DocumentDetailResponse`` with predictable defaults for tests."""

    timestamp = datetime.now(UTC)
    return DocumentDetailResponse(
        id="doc-1",
        title="Example Document",
        collection="sermons",
        source_type="sermon",
        authors=["Author"],
        doi=None,
        venue=None,
        year=None,
        topics=None,
        primary_topic=None,
        enrichment_version=None,
        provenance_score=None,
        abstract=None,
        source_url=None,
        metadata=metadata,
        created_at=timestamp,
        updated_at=timestamp,
        passages=[],
    )


def test_build_document_export_includes_requested_metadata_fields() -> None:
    """Nested metadata selectors should retain the metadata block in exports."""

    document = _make_document({"title": "Doc Title", "extra": "ignored"})
    response = DocumentExportResponse(
        filters=DocumentExportFilters(),
        include_passages=True,
        limit=None,
        cursor=None,
        next_cursor=None,
        total_documents=1,
        total_passages=0,
        documents=[document],
    )

    _manifest, records = build_document_export(
        response,
        include_passages=False,
        include_text=False,
        fields={"metadata.title"},
    )

    assert len(records) == 1
    record = records[0]
    assert set(record.keys()) == {"metadata"}
    assert record["metadata"] == {"title": "Doc Title"}
