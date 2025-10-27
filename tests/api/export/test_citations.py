"""Tests for citation export utilities."""

from __future__ import annotations

import pytest

from theo.infrastructure.api.app.export.citations import (
    CitationSource,
    format_citation,
    build_citation_export,
)


@pytest.fixture
def sample_document():
    """Sample document data for citation testing."""
    return {
        "id": "doc-test-1",
        "title": "Theology of the Cross",
        "authors": ["Martin Luther", "Philip Melanchthon"],
        "year": 1518,
        "venue": "Journal of Reformation Studies",
        "collection": "Reformation Theology",
        "source_type": "article",
        "doi": "10.1234/reformation.1518",
        "source_url": "https://example.com/theology-cross",
        "abstract": "An examination of Luther's theology of the cross.",
        "publisher": "Wittenberg Press",
        "location": "Wittenberg",
        "volume": "12",
        "issue": "2",
        "pages": "45-78",
    }


def test_citation_source_from_object(sample_document):
    """Test creating CitationSource from document object."""
    source = CitationSource.from_object(sample_document)

    assert source.document_id == "doc-test-1"
    assert source.title == "Theology of the Cross"
    assert source.authors == ["Martin Luther", "Philip Melanchthon"]
    assert source.year == 1518
    assert source.venue == "Journal of Reformation Studies"
    assert source.doi == "https://doi.org/10.1234/reformation.1518"
    assert source.source_url == "https://example.com/theology-cross"


def test_citation_source_from_minimal_object():
    """Test CitationSource with minimal data."""
    minimal_doc = {"id": "minimal-1", "title": "Untitled"}
    source = CitationSource.from_object(minimal_doc)

    assert source.document_id == "minimal-1"
    assert source.title == "Untitled"
    assert source.authors is None
    assert source.year is None


def test_citation_source_handles_case_insensitive_fields():
    """Ensure CitationSource picks up fields regardless of key capitalisation."""
    document = {
        "ID": "case-1",
        "TITLE": "Case Sensitivity in Citations",
        "AUTHORS": ["Doe, Jane"],
        "YEAR": "1999",
        "VENUE": "Journal of Testing",
        "DOI": "DOI:10.5555/case",
        "Metadata": {
            "Publisher": "Test Press",
            "LOCATION": "New York",
            "KEYWORDS": ["Testing", "Citations"],
        },
    }

    source = CitationSource.from_object(document)

    assert source.document_id == "case-1"
    assert source.title == "Case Sensitivity in Citations"
    assert source.authors == ["Doe, Jane"]
    assert source.year == 1999
    assert source.venue == "Journal of Testing"
    assert source.doi == "https://doi.org/10.5555/case"
    assert source.publisher == "Test Press"
    assert source.location == "New York"
    assert source.topics == ["Testing", "Citations"]


def test_citation_source_normalizes_doi():
    """Test DOI normalization in CitationSource."""
    # Various DOI formats should normalize to https://doi.org/...
    test_cases = [
        ("10.1234/test", "https://doi.org/10.1234/test"),
        ("doi:10.1234/test", "https://doi.org/10.1234/test"),
        ("https://doi.org/10.1234/test", "https://doi.org/10.1234/test"),
        ("http://dx.doi.org/10.1234/test", "https://doi.org/10.1234/test"),
        ("doi.org/10.1234/test", "https://doi.org/10.1234/test"),
    ]

    for input_doi, expected_doi in test_cases:
        doc = {"id": "test", "doi": input_doi}
        source = CitationSource.from_object(doc)
        assert source.doi == expected_doi


def test_format_citation_apa():
    """Test APA citation formatting."""
    source = CitationSource(
        document_id="apa-test",
        title="Systematic Theology",
        authors=["Berkhof, Louis"],
        year=1938,
        venue="Theological Studies",
        volume="5",
        pages="123-145",
    )

    citation_text, csl_entry = format_citation(source, style="apa")

    assert "Berkhof, L." in citation_text
    assert "(1938)" in citation_text
    assert "Systematic Theology" in citation_text
    assert "Theological Studies" in citation_text
    assert csl_entry["type"] == "article-journal"


def test_format_citation_chicago():
    """Test Chicago citation formatting."""
    source = CitationSource(
        document_id="chicago-test",
        title="The Institutes",
        authors=["Calvin, John"],
        year=1536,
        publisher="Bonnet",
        location="Geneva",
    )

    citation_text, csl_entry = format_citation(source, style="chicago")

    assert "Calvin, John" in citation_text
    assert "The Institutes" in citation_text
    assert "1536" in citation_text
    assert csl_entry["type"] == "article-journal"


def test_format_citation_sbl():
    """Test SBL citation formatting."""
    source = CitationSource(
        document_id="sbl-test",
        title="Commentary on Romans",
        authors=["Cranfield, C. E. B."],
        year=1975,
        venue="ICC",
        pages="1-50",
    )

    citation_text, csl_entry = format_citation(source, style="sbl")

    assert "Cranfield, C. E. B." in citation_text
    assert '"Commentary on Romans"' in citation_text
    assert "1975" in citation_text


def test_format_citation_bibtex():
    """Test BibTeX citation formatting."""
    source = CitationSource(
        document_id="bibtex-test",
        title="Theology Primer",
        authors=["Author, Test"],
        year=2020,
        venue="Test Journal",
    )

    citation_text, csl_entry = format_citation(source, style="bibtex")

    assert "@article{bibtex-test," in citation_text
    assert "title = {Theology Primer}" in citation_text
    assert "author = {Author, Test}" in citation_text
    assert "year = {2020}" in citation_text
    assert "journal = {Test Journal}" in citation_text


def test_format_citation_with_anchors():
    """Test citation formatting with verse anchors."""
    source = CitationSource(
        document_id="anchor-test",
        title="Biblical Commentary",
        authors=["Scholar, Jane"],
        year=2022,
    )

    anchors = [
        {"osis": "John.1.1", "label": "p.45", "snippet": "In the beginning..."},
        {"osis": "John.1.14", "label": "p.47", "snippet": "The Word became flesh..."},
    ]

    citation_text, csl_entry = format_citation(source, style="apa", anchors=anchors)

    assert "Anchors:" in citation_text
    assert "John.1.1" in citation_text
    assert "John.1.14" in citation_text
    assert "note" in csl_entry
    assert "Anchors:" in csl_entry["note"]


def test_format_citation_csl_json():
    """Test CSL-JSON formatting."""
    source = CitationSource(
        document_id="csl-test",
        title="Test Article",
        authors=["Doe, John"],
        year=2023,
    )

    citation_text, csl_entry = format_citation(source, style="csl-json")

    # Should return JSON string
    assert '"id": "csl-test"' in citation_text
    assert '"title": "Test Article"' in citation_text
    assert csl_entry["id"] == "csl-test"
    assert csl_entry["title"] == "Test Article"


def test_format_citation_multiple_authors():
    """Test citation formatting with multiple authors."""
    source = CitationSource(
        document_id="multi-author",
        title="Collaborative Work",
        authors=["First, Author", "Second, Author", "Third, Author"],
        year=2021,
    )

    apa_text, _ = format_citation(source, style="apa")
    assert "First, A., Second, A., & Third, A." in apa_text

    chicago_text, _ = format_citation(source, style="chicago")
    assert "First, Author, Second, Author, and Third, Author" in chicago_text


def test_format_citation_no_author():
    """Test citation formatting without authors."""
    source = CitationSource(
        document_id="no-author",
        title="Anonymous Work",
        year=2020,
        publisher="Anonymous Press",
    )

    apa_text, _ = format_citation(source, style="apa")
    # Should use publisher as author fallback
    assert "Anonymous Press" in apa_text or "Untitled" in apa_text


def test_build_citation_export():
    """Test building complete citation export."""
    documents = [
        {
            "id": "export-1",
            "title": "First Document",
            "authors": ["Author One"],
            "year": 2020,
        },
        {
            "id": "export-2",
            "title": "Second Document",
            "authors": ["Author Two"],
            "year": 2021,
        },
    ]

    manifest, records, csl_entries = build_citation_export(
        documents,
        style="apa",
        anchors=None,
        filters={"collection": "Test"},
    )

    # Check manifest
    assert manifest.type == "citations"
    assert manifest.totals["citations"] == 2
    assert manifest.filters["collection"] == "Test"
    assert manifest.mode == "apa"

    # Check records
    assert len(records) == 2
    assert records[0]["kind"] == "citation"
    assert records[0]["document_id"] == "export-1"
    assert records[0]["style"] == "apa"
    assert "Author One" in records[0]["citation"]

    # Check CSL entries
    assert len(csl_entries) == 2
    assert csl_entries[0]["id"] == "export-1"
    assert csl_entries[1]["id"] == "export-2"


def test_build_citation_export_with_anchors():
    """Test citation export with verse anchors."""
    documents = [
        {
            "id": "with-anchors",
            "title": "Commentary",
            "authors": ["Scholar, Jane"],
            "year": 2022,
        }
    ]

    anchors = {
        "with-anchors": [
            {"osis": "Rom.3.23", "label": "p.100"},
            {"osis": "Rom.6.23", "label": "p.150"},
        ]
    }

    manifest, records, csl_entries = build_citation_export(
        documents,
        style="apa",
        anchors=anchors,
    )

    assert len(records) == 1
    assert "anchors" in records[0]
    assert len(records[0]["anchors"]) == 2
    assert records[0]["anchors"][0]["osis"] == "Rom.3.23"


def test_citation_source_handles_array_authors():
    """Test CitationSource handles authors as array."""
    doc = {
        "id": "test",
        "authors": ["Calvin, John", "Luther, Martin"],
    }

    source = CitationSource.from_object(doc)
    assert source.authors == ["Calvin, John", "Luther, Martin"]


def test_citation_source_handles_string_author():
    """Test CitationSource converts single author string to list."""
    doc = {
        "id": "test",
        "authors": "Single Author",
    }

    source = CitationSource.from_object(doc)
    assert source.authors == ["Single Author"]


def test_citation_with_doi_and_url():
    """Test that DOI is preferred over URL in citations."""
    source = CitationSource(
        document_id="doi-url-test",
        title="Test",
        authors=["Author"],
        year=2023,
        doi="https://doi.org/10.1234/test",
        source_url="https://example.com/fallback",
    )

    apa_text, _ = format_citation(source, style="apa")

    # DOI should be included, URL should not
    assert "https://doi.org/10.1234/test" in apa_text
    assert "example.com/fallback" not in apa_text


def test_citation_url_without_doi():
    """Test that URL is used when DOI is absent."""
    source = CitationSource(
        document_id="url-only-test",
        title="Test",
        authors=["Author"],
        year=2023,
        source_url="https://example.com/article",
    )

    apa_text, _ = format_citation(source, style="apa")
    assert "https://example.com/article" in apa_text
