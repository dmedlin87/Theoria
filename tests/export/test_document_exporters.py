from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.infrastructure.api.app.export import formatters  # noqa: E402
from theo.infrastructure.api.app.export.citations import (  # noqa: E402
    CitationSource,
    build_citation_export,
)
from theo.infrastructure.api.app.models.base import Passage  # noqa: E402
from theo.infrastructure.api.app.models.documents import (  # noqa: E402
    DocumentDetailResponse,
)
from theo.infrastructure.api.app.models.export import (  # noqa: E402
    DocumentExportFilters,
    DocumentExportResponse,
)


@pytest.fixture()
def document_export_payload():
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    document = DocumentDetailResponse(
        id="doc-1",
        title="Example Document",
        source_type="article",
        collection="theology",
        authors=["Jane Doe", "John Roe"],
        doi="10.1234/example",
        venue="TheoConf",
        year=2023,
        created_at=now,
        updated_at=now,
        provenance_score=82,
        source_url="https://example.com/doc-1",
        channel=None,
        video_id=None,
        duration_seconds=None,
        storage_path=None,
        abstract="An example abstract",
        topics=["grace"],
        enrichment_version=2,
        primary_topic="Grace",
        metadata={"publisher": "Theo Press", "pages": "10-12"},
        passages=[
            Passage(
                id="passage-1",
                document_id="doc-1",
                osis_ref="John.1.1",
                page_no=1,
                t_start=None,
                t_end=None,
                text="In the beginning was the Word.",
                meta={"snippet": "In the beginning was the Word."},
            )
        ],
    )
    response = DocumentExportResponse(
        filters=DocumentExportFilters(collection="theology"),
        include_passages=True,
        limit=None,
        cursor="doc-1",
        next_cursor=None,
        total_documents=1,
        total_passages=1,
        documents=[document],
    )
    manifest, records = formatters.build_document_export(
        response,
        include_passages=True,
        include_text=True,
        export_id="export-fixture",
    )
    fixed_manifest = manifest.model_copy(
        update={"created_at": now, "app_git_sha": "abc1234"}
    )
    return fixed_manifest, records


@pytest.mark.parametrize(
    "output_format, filename, binary",
    [
        ("html", "document_export_bundle.html", False),
        ("obsidian", "document_export_bundle.md", False),
        ("pdf", "document_export_bundle.pdf", True),
    ],
)
def test_render_bundle_matches_golden(document_export_payload, output_format, filename, binary):
    manifest, records = document_export_payload
    body, media_type = formatters.render_bundle(
        manifest, records, output_format=output_format
    )
    golden_path = PROJECT_ROOT / "tests" / "export" / "golden" / filename
    if binary:
        assert isinstance(body, (bytes, bytearray))
        assert media_type == "application/pdf"
        expected = golden_path.read_bytes()
        assert body == expected
    else:
        assert isinstance(body, str)
        expected = golden_path.read_text("utf-8")
        assert body == expected


def test_json_and_ndjson_exports_consistent(document_export_payload):
    manifest, records = document_export_payload
    json_body, _ = formatters.render_bundle(manifest, records, output_format="json")
    ndjson_body, _ = formatters.render_bundle(manifest, records, output_format="ndjson")

    payload = json.loads(json_body)
    assert payload["manifest"]["export_id"] == manifest.export_id

    ndjson_lines = ndjson_body.strip().splitlines()
    assert ndjson_lines
    # First line should be the manifest
    parsed_manifest = json.loads(ndjson_lines[0])
    assert parsed_manifest == json.loads(manifest.model_dump_json())
    # Remaining lines map to records; ensure streaming order matches JSON payload
    parsed_records = [json.loads(line) for line in ndjson_lines[1:]]
    assert parsed_records == payload["records"]
    assert ndjson_body.endswith("\n")


def test_citation_export_renders_expected_fields():
    fixtures_dir = PROJECT_ROOT / "fixtures" / "citations"
    documents = json.loads((fixtures_dir / "documents.json").read_text("utf-8"))
    anchors = json.loads((fixtures_dir / "anchors.json").read_text("utf-8"))

    manifest, records, _ = build_citation_export(
        documents,
        style="apa",
        anchors=anchors,
        filters={"osis": "John.1.1"},
        export_id="citation-export-fixture",
    )
    fixed_manifest = manifest.model_copy(
        update={"created_at": datetime(2024, 1, 1, tzinfo=timezone.utc)}
    )
    json_body, media_type = formatters.render_bundle(
        fixed_manifest, records, output_format="json"
    )
    assert media_type == "application/json"
    payload = json.loads(json_body)
    assert payload["manifest"]["type"] == "citations"
    first_entry = payload["records"][0]
    assert "Jane Doe" in first_entry["citation"]
    assert "Theology of Grace" in first_entry["citation"]
    assert "csl" in first_entry


def test_render_bundle_unsupported_format(document_export_payload):
    manifest, records = document_export_payload
    with pytest.raises(ValueError):
        formatters.render_bundle(manifest, records, output_format="yaml")


def test_citation_source_missing_identifier_raises():
    with pytest.raises(ValueError):
        CitationSource.from_object({"title": "Missing identifier"})
