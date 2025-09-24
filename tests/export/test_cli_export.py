import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager

import pytest
from click.testing import CliRunner

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.models.base import Passage
from theo.services.api.app.models.documents import DocumentDetailResponse
from theo.services.api.app.models.export import (
    DocumentExportFilters,
    DocumentExportResponse,
    ExportedDocumentSummary,
    SearchExportResponse,
    SearchExportRow,
)
from theo.services.api.app.models.search import HybridSearchFilters
from theo.services.cli import export_data as cli  # noqa: E402


@contextmanager
def _dummy_session_scope():
    yield object()


def _build_document_export() -> DocumentExportResponse:
    now = datetime.now(timezone.utc)
    document = DocumentDetailResponse(
        id="doc-1",
        title="Example",
        source_type="markdown",
        collection="sermons",
        authors=["Jane"],
        doi=None,
        venue=None,
        year=2024,
        created_at=now,
        updated_at=now,
        source_url=None,
        channel=None,
        video_id=None,
        duration_seconds=None,
        storage_path=None,
        abstract=None,
        topics=None,
        enrichment_version=None,
        provenance_score=None,
        metadata=None,
        passages=[],
    )
    return DocumentExportResponse(
        filters=DocumentExportFilters(collection="sermons"),
        include_passages=False,
        limit=None,
        total_documents=1,
        total_passages=0,
        documents=[document],
    )


def _build_search_export() -> SearchExportResponse:
    passage = Passage(
        id="passage-1",
        document_id="doc-1",
        text="Example passage text",
        osis_ref=None,
        page_no=1,
        t_start=None,
        t_end=None,
        score=0.9,
        meta=None,
    )
    row = SearchExportRow(
        rank=1,
        score=0.9,
        passage=passage,
        document=ExportedDocumentSummary(
            id="doc-1",
            title="Example",
            source_type="markdown",
            collection="sermons",
            authors=["Jane"],
            doi=None,
            venue=None,
            year=2024,
            source_url=None,
        ),
    )
    return SearchExportResponse(
        query="grace",
        osis=None,
        filters=HybridSearchFilters(collection="sermons"),
        total_results=1,
        results=[row],
    )


def test_search_export_command_writes_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_session_scope", _dummy_session_scope)
    monkeypatch.setattr(cli, "export_search_results", lambda session, request: _build_search_export())

    runner = CliRunner()
    result = runner.invoke(cli.export, ["search", "--query", "grace"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["total_results"] == 1
    assert payload["results"][0]["document"]["collection"] == "sermons"


def test_document_export_command_supports_ndjson(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_session_scope", _dummy_session_scope)
    monkeypatch.setattr(cli, "export_documents", lambda session, filters, include_passages, limit: _build_document_export())

    runner = CliRunner()
    result = runner.invoke(
        cli.export,
        [
            "documents",
            "--collection",
            "sermons",
            "--format",
            "ndjson",
            "--no-include-passages",
        ],
    )

    assert result.exit_code == 0
    lines = [json.loads(line) for line in result.output.strip().splitlines()]
    assert lines[0]["kind"] == "metadata"
    assert lines[1]["kind"] == "document"
    assert lines[1]["collection"] == "sermons"
