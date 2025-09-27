from __future__ import annotations

from theo.services.api.app.research import (
    fallacy_detect,
    historicity_search,
    report_build,
    variants_apparatus,
)


def test_variants_apparatus_returns_entries_for_single_verse() -> None:
    readings = variants_apparatus("John.1.1")
    assert readings
    assert {entry.category for entry in readings} >= {"manuscript", "translation"}


def test_variants_apparatus_category_filter() -> None:
    readings = variants_apparatus("John.1.1", categories=["manuscript"])
    assert readings
    assert all(entry.category.lower() == "manuscript" for entry in readings)


def test_historicity_search_honors_year_filters() -> None:
    results = historicity_search("bethlehem", year_from=2015)
    assert results
    assert all(entry.year is None or entry.year >= 2015 for entry in results)


def test_historicity_search_returns_empty_for_unknown_query() -> None:
    results = historicity_search("nonexistenttopic")
    assert results == []


def test_fallacy_detect_thresholds_matches() -> None:
    text = (
        "Leading experts agree that this is reliable, and all historians confirm"
        " it while critics claim that believers worship legends."
    )
    hits = fallacy_detect(text, min_confidence=0.5)
    assert hits
    assert hits[0].id == "appeal-to-authority"
    assert hits[0].confidence >= 0.6


def test_report_build_combines_sections() -> None:
    report = report_build(
        "John.1.1",
        stance="apologetic",
        claims=[{"statement": "The Logos is divine."}],
        historicity_query="logos",
        include_fallacies=True,
        narrative_text="Leading experts agree this was foretold.",
    )
    section_titles = [section.title for section in report.sections]
    assert "Stability of the Text" in section_titles[0]
    assert report.meta["variant_count"] > 0
    assert report.meta["citation_count"] >= 1
    assert report.meta["fallacy_count"] >= 0
