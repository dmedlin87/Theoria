"""Tests for the metadata enrichment helpers."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session, sessionmaker

from theo.adapters.persistence.models import Document
from theo.infrastructure.api.app.enrich.metadata import (
    MetadataEnricher,
    _dedupe_preserve_order,
    _extract_doi_from_url,
    _normalise_doi,
    _slugify,
)


def _make_enricher(tmp_path) -> MetadataEnricher:
    settings = SimpleNamespace(fixtures_root=tmp_path, user_agent="pytest-agent/1.0")
    return MetadataEnricher(settings=settings)


def _should_not_perform_http(*_args, **_kwargs):
    raise AssertionError("HTTP fetch should not be used when fixture exists")


def test_slugify_normalises_values() -> None:
    assert _slugify(" DOI:10.123/ABC ") == "doi_10_123_abc"
    assert _slugify("  Mixed CASE & symbols !!  ") == "mixed_case_symbols"
    assert _slugify("   ") == ""


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("https://doi.org/10.123/ABC", "10.123/ABC"),
        ("http://doi.org/10.123/abc", "10.123/abc"),
        ("doi:10.123/XYZ", "10.123/XYZ"),
        ("10.123/def", "10.123/def"),
        ("", None),
        (None, None),
    ],
)
def test_normalise_doi_variants(raw, expected) -> None:
    assert _normalise_doi(raw) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://doi.org/10.123/ABC", "10.123/ABC"),
        ("https://example.com/path", None),
        ("http://doi.org/10.456/def", "10.456/def"),
    ],
)
def test_extract_doi_from_url(url, expected) -> None:
    assert _extract_doi_from_url(url) == expected


def test_dedupe_preserve_order_filters_and_preserves() -> None:
    items = ["Alpha", "", "Beta", "Alpha", "beta", None, "Gamma", "Beta"]
    assert _dedupe_preserve_order(items) == ["Alpha", "Beta", "beta", "Gamma"]


def test_extract_doi_prefers_document_fields() -> None:
    document = Document(
        doi=" doi:10.1111/PRIMARY ",
        bib_json={"DOI": "https://doi.org/10.2222/SECOND", "doi": "10.3333/third"},
        source_url="https://doi.org/10.4444/fourth",
    )
    enricher = MetadataEnricher(settings=SimpleNamespace(user_agent="pytest-agent"))

    assert enricher._extract_doi(document) == "10.1111/PRIMARY"


def test_build_queries_orders_identifier_types() -> None:
    document = Document(
        doi="https://doi.org/10.5555/XYZ",
        bib_json={"DOI": "10.5555/SHADOW"},
        source_url="https://doi.org/10.5555/xyz",
        title="A Sample Title",
    )
    enricher = MetadataEnricher(settings=SimpleNamespace(user_agent="pytest-agent"))

    assert list(enricher._build_queries(document)) == [
        ("doi", "10.5555/XYZ"),
        ("url", "https://doi.org/10.5555/xyz"),
        ("title", "A Sample Title"),
    ]


def test_try_openalex_uses_fixture(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    enricher = _make_enricher(tmp_path)
    monkeypatch.setattr(enricher, "_http_get_json", _should_not_perform_http)

    data = {
        "display_name": "Fixture Title",
        "doi": "10.7777/OPEN",
        "authorships": [
            {"author": {"display_name": "Author One"}},
            {"author": {"display_name_raw": "Author Two"}},
        ],
        "host_venue": {"display_name": "Open Venue"},
        "publication_year": 2022,
        "abstract_inverted_index": {"hello": [0], "world": [1]},
        "concepts": [{"display_name": "Theology"}, {"display_name": "History"}],
    }

    fixture_dir = tmp_path / "openalex"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "doi_10_7777_open.json").write_text(json.dumps(data), encoding="utf-8")

    result = enricher._try_openalex([("doi", "10.7777/open")])

    assert result is not None
    assert result.provider == "openalex"
    assert result.doi == "10.7777/OPEN"
    assert result.title == "Fixture Title"
    assert result.authors == ["Author One", "Author Two"]
    assert result.topics == ["Theology", "History"]
    assert result.primary_topic == "Theology"


def test_try_crossref_uses_fixture(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    enricher = _make_enricher(tmp_path)
    monkeypatch.setattr(enricher, "_http_get_json", _should_not_perform_http)

    data = {
        "message": {
            "title": ["Crossref Title"],
            "DOI": "10.8888/CROSS",
            "author": [{"given": "Chris", "family": "Cross"}],
            "container-title": ["Crossref Venue"],
            "abstract": "<p>Abstract text</p>",
            "subject": ["History", "Theology"],
            "issued": {"date-parts": [[2023]]},
        }
    }

    fixture_dir = tmp_path / "crossref"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "doi_10_8888_cross.json").write_text(json.dumps(data), encoding="utf-8")

    result = enricher._try_crossref([("doi", "10.8888/cross")])

    assert result is not None
    assert result.provider == "crossref"
    assert result.doi == "10.8888/CROSS"
    assert result.title == "Crossref Title"
    assert result.authors == ["Chris Cross"]
    assert result.venue == "Crossref Venue"
    assert result.year == 2023
    assert result.primary_topic == "History"
    assert result.topics == ["History", "Theology"]


def test_enrich_document_persists_changes(
    api_engine, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    SessionLocal = sessionmaker(bind=api_engine)
    with SessionLocal() as session:  # type: Session
        document = Document(
            doi="10.9999/initial",
            bib_json={"existing": "value", "enrichment": {"other": {"flag": True}}},
        )
        session.add(document)
        session.commit()

        enricher = _make_enricher(tmp_path)
        monkeypatch.setattr(enricher, "_http_get_json", _should_not_perform_http)

        data = {
            "display_name": "Stored Title",
            "doi": "10.9999/INITIAL",
            "authorships": [{"author": {"display_name": "Primary Author"}}],
            "host_venue": {"display_name": "Fixture Journal"},
            "publication_year": 2020,
            "abstract_inverted_index": {"test": [0], "case": [1]},
            "concepts": [{"display_name": "Divinity"}],
        }

        fixture_dir = tmp_path / "openalex"
        fixture_dir.mkdir(parents=True)
        (fixture_dir / "doi_10_9999_initial.json").write_text(
            json.dumps(data), encoding="utf-8"
        )

        assert enricher.enrich_document(session, document) is True

        reloaded = session.get(Document, document.id)
        assert reloaded is not None
        assert reloaded.title == "Stored Title"
        assert reloaded.doi == "10.9999/INITIAL"
        assert reloaded.authors == ["Primary Author"]
        assert reloaded.venue == "Fixture Journal"
        assert reloaded.year == 2020
        assert reloaded.abstract == "test case"
        assert reloaded.topics == {"primary": "Divinity", "all": ["Divinity"]}
        assert reloaded.enrichment_version == MetadataEnricher.ENRICHMENT_VERSION

        assert reloaded.bib_json["existing"] == "value"
        assert reloaded.bib_json["enrichment"]["other"] == {"flag": True}
        assert reloaded.bib_json["enrichment"]["openalex"] == data
        assert reloaded.bib_json["primary_topic"] == "Divinity"
