"""Regression tests covering CSL citation identifiers."""

import json

import pytest

from theo.infrastructure.api.app.export.citations import CitationSource, format_citation


def test_citation_source_uses_document_id_for_csl_citekey() -> None:
    source = CitationSource.from_object(
        {
            "document_id": "doc-001",
            "title": "The Logos and Creation",
            "authors": ["Jane Doe"],
            "year": 2024,
            "source_type": "journal article",
        }
    )

    citation_text, csl_entry = format_citation(source, style="csl-json", anchors=[])

    assert csl_entry["id"] == "doc-001"
    assert json.loads(citation_text)["id"] == "doc-001"
    assert csl_entry["title"] == "The Logos and Creation"
    assert csl_entry["author"][0] == {"family": "Doe", "given": "Jane"}


def test_citation_source_requires_identifier() -> None:
    with pytest.raises(ValueError):
        CitationSource.from_object({"title": "Missing id"})
