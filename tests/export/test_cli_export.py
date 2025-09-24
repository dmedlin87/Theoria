import csv
import json
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

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
from theo.services.api.app.models.search import HybridSearchFilters, HybridSearchRequest
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
        doi="10.1234/example",
        venue="Theo Journal",
        year=2024,
        created_at=now,
        updated_at=now,
        source_url="https://example.test",
        channel=None,
        video_id=None,
        duration_seconds=None,
        storage_path=None,
        abstract="An illustrative sample.",
        topics=["Theology", "Grace"],
        enrichment_version=2,
        primary_topic="Theology",
        provenance_score=7,
        metadata={"primary_topic": "Theology"},
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


def _build_search_export(next_cursor: str | None = "passage-1") -> SearchExportResponse:
    passage = Passage(
        id="passage-1",
        document_id="doc-1",
        text="Example passage text",
        osis_ref="John.1.1",
        page_no=1,
        t_start=0.0,
        t_end=5.0,
        score=0.9,
        meta={"snippet": "Example snippet"},
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
            doi="10.1234/example",
            venue="Theo Journal",
            year=2024,
            topics=["Grace"],
            primary_topic="Grace",
            enrichment_version=3,
            provenance_score=8,
            source_url="https://example.test",
        ),
        snippet="Example snippet",
    )
    return SearchExportResponse(
        query="grace",
        osis="John.1.1",
        filters=HybridSearchFilters(collection="sermons"),
        total_results=1,
        next_cursor=next_cursor,
        results=[row],
    )


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(cli, "STATE_DIR", tmp_path / "export_state")
    return cli.STATE_DIR


@pytest.fixture(autouse=True)
def _patch_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_session_scope", _dummy_session_scope)


def test_search_export_cli_csv_includes_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "export_search_results", lambda session, request: _build_search_export())

    runner = CliRunner()
    result = runner.invoke(
        cli.export,
        [
            "search",
            "--query",
            "grace",
            "--osis",
            "John.1.1",
            "--format",
            "csv",
            "--export-id",
            "search-demo",
        ],
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.strip().splitlines() if line]
    manifest = json.loads(lines[0])
    assert manifest["type"] == "search"
    assert manifest["filters"]["osis"] == "John.1.1"
    assert manifest["totals"]["results"] == 1
    csv_reader = csv.DictReader(lines[1:])
    assert csv_reader.fieldnames == [
        "kind",
        "rank",
        "score",
        "document_id",
        "passage_id",
        "title",
        "collection",
        "source_type",
        "authors",
        "doi",
        "venue",
        "year",
        "topics",
        "primary_topic",
        "enrichment_version",
        "provenance_score",
        "osis_ref",
        "page_no",
        "t_start",
        "t_end",
        "snippet",
    ]
    row = next(csv_reader)
    assert row["document_id"] == "doc-1"
    state_file = cli.STATE_DIR / "search-demo.json"
    assert state_file.exists()
    saved_manifest = json.loads(state_file.read_text("utf-8"))
    assert saved_manifest["next_cursor"] == "passage-1"


def test_search_export_cli_requests_extra_row(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, int | None] = {}

    def _capture_request(session, request: HybridSearchRequest) -> SearchExportResponse:
        captured["k"] = request.k
        captured["limit"] = request.limit
        return _build_search_export()

    monkeypatch.setattr(cli, "export_search_results", _capture_request)

    runner = CliRunner()
    result = runner.invoke(
        cli.export,
        [
            "search",
            "--query",
            "grace",
            "--limit",
            "25",
        ],
    )

    assert result.exit_code == 0
    assert captured["limit"] == 25
    assert captured["k"] == 26


def test_document_export_cli_ndjson_contains_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli,
        "export_documents",
        lambda session, filters, include_passages, limit, cursor=None: _build_document_export(),
    )

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
            "--export-id",
            "doc-demo",
        ],
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.strip().splitlines() if line]
    manifest = json.loads(lines[0])
    assert manifest["type"] == "documents"
    assert manifest["totals"]["documents"] == 1
    record = json.loads(lines[1])
    assert record["kind"] == "document"
    assert record["primary_topic"] == "Theology"
    assert record["doi"] == "10.1234/example"
    state_file = cli.STATE_DIR / "doc-demo.json"
    assert state_file.exists()


def test_search_manifest_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[HybridSearchRequest] = []

    def _recorder(session, request: HybridSearchRequest) -> SearchExportResponse:
        calls.append(request)
        return _build_search_export(next_cursor=None)

    monkeypatch.setattr(cli, "export_search_results", _recorder)

    runner = CliRunner()
    result = runner.invoke(
        cli.export,
        [
            "search",
            "--query",
            "grace",
            "--export-id",
            "resume-demo",
            "--metadata-only",
        ],
    )

    assert result.exit_code == 0
    assert calls[0].cursor is None
    state_file = cli.STATE_DIR / "resume-demo.json"
    manifest = json.loads(state_file.read_text("utf-8"))
    assert manifest["totals"]["returned"] == 0
    assert manifest["next_cursor"] is None
