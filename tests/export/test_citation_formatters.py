from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from unittest.mock import Mock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.export.citations import (  # noqa: E402
    CitationSource,
    build_citation_export,
    render_citation_markdown,
)


@pytest.fixture()
def citation_fixture_data() -> tuple[list[dict[str, object]], dict[str, list[dict[str, object]]], Path]:
    fixtures_dir = PROJECT_ROOT / "fixtures" / "citations"
    documents = json.loads((fixtures_dir / "documents.json").read_text("utf-8"))
    anchors = json.loads((fixtures_dir / "anchors.json").read_text("utf-8"))
    return documents, anchors, fixtures_dir


def test_build_citation_export_apa(citation_fixture_data) -> None:
    documents, anchors, fixtures_dir = citation_fixture_data
    manifest, records, csl_entries = build_citation_export(
        documents,
        style="apa",
        anchors=anchors,
        filters={"osis": "John.1.1"},
        export_id="fixture-export",
    )

    expected = (
        fixtures_dir / "expected_apa.txt"
    ).read_text("utf-8").strip().splitlines()
    actual = [record["citation"] for record in records]
    assert actual == expected
    assert all("csl" in record for record in records)
    assert csl_entries[0]["DOI"] == "https://doi.org/10.1234/example"
    assert manifest.type == "citations"
    assert manifest.mode == "apa"


def test_build_citation_export_chicago(citation_fixture_data) -> None:
    documents, anchors, fixtures_dir = citation_fixture_data
    _, records, _ = build_citation_export(
        documents,
        style="chicago",
        anchors=anchors,
        filters={"osis": "John.1.1"},
        export_id="fixture-export",
    )
    expected = (
        fixtures_dir / "expected_chicago.txt"
    ).read_text("utf-8").strip().splitlines()
    assert [record["citation"] for record in records] == expected


def test_build_citation_export_sbl(citation_fixture_data) -> None:
    documents, anchors, fixtures_dir = citation_fixture_data
    _, records, _ = build_citation_export(
        documents,
        style="sbl",
        anchors=anchors,
        filters={"osis": "John.1.1"},
        export_id="fixture-export",
    )
    expected = (
        fixtures_dir / "expected_sbl.txt"
    ).read_text("utf-8").strip().splitlines()
    assert [record["citation"] for record in records] == expected


def test_build_citation_export_bibtex(citation_fixture_data) -> None:
    documents, anchors, fixtures_dir = citation_fixture_data
    _, records, _ = build_citation_export(
        documents,
        style="bibtex",
        anchors=anchors,
        filters={"osis": "John.1.1"},
        export_id="fixture-export",
    )
    expected_text = (fixtures_dir / "expected_bibtex.txt").read_text("utf-8").strip()
    expected_entries = [entry.strip() for entry in expected_text.split("\n\n") if entry.strip()]
    assert [record["citation"] for record in records] == expected_entries


def test_render_citation_markdown_matches_fixture(citation_fixture_data) -> None:
    documents, anchors, fixtures_dir = citation_fixture_data
    manifest, records, _ = build_citation_export(
        documents,
        style="apa",
        anchors=anchors,
        filters={"osis": "John.1.1"},
        export_id="fixture-export",
    )
    fixed_manifest = manifest.model_copy(
        update={"created_at": datetime(2024, 1, 1, tzinfo=timezone.utc)}
    )
    markdown = render_citation_markdown(fixed_manifest, records)
    expected_markdown = (fixtures_dir / "expected_markdown.md").read_text("utf-8")
    assert markdown == expected_markdown


def test_citation_source_normalises_uppercase_prefix() -> None:
    source = CitationSource.from_object({"document_id": "doc", "doi": "DOI:10.1000/ABC"})
    assert source.doi == "https://doi.org/10.1000/ABC"


def test_citation_source_handles_bare_doi_domain() -> None:
    source = CitationSource.from_object({"document_id": "doc", "doi": "doi.org/10.1000/xyz"})
    assert source.doi == "https://doi.org/10.1000/xyz"


def test_build_citation_export_invokes_zotero_callback(citation_fixture_data) -> None:
    documents, anchors, _ = citation_fixture_data
    callback = Mock()
    build_citation_export(
        documents,
        style="apa",
        anchors=anchors,
        zotero_callback=callback,
    )
    assert callback.call_count == len(documents)
    first_call_args = callback.call_args_list[0].args
    assert first_call_args[0]["id"] == documents[0]["id"]
