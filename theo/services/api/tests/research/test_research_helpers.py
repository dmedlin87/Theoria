from __future__ import annotations

from theo.application.research import ResearchService
from theo.domain.research import fallacy_detect, historicity_search, variants_apparatus


class _StubResearchNoteRepository:
    """Minimal repository implementation for research service tests."""

    def create(self, draft, *, commit: bool = True):  # pragma: no cover - not used
        raise NotImplementedError("create should not be invoked in helper tests")

    def preview(self, draft):  # pragma: no cover - not used
        raise NotImplementedError("preview should not be invoked in helper tests")

    def list_for_osis(
        self,
        osis: str,
        *,
        stance: str | None = None,
        claim_type: str | None = None,
        tag: str | None = None,
        min_confidence: float | None = None,
    ) -> list:
        return []

    def update(self, note_id, changes, *, evidences=None):  # pragma: no cover - not used
        raise NotImplementedError("update should not be invoked in helper tests")

    def delete(self, note_id):  # pragma: no cover - not used
        raise NotImplementedError("delete should not be invoked in helper tests")


def _research_service() -> ResearchService:
    return ResearchService(_StubResearchNoteRepository())


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
    service = _research_service()
    report = service.report_build(
        "John.1.1",
        stance="apologetic",
        claims=[{"statement": "The Logos is divine."}],
        historicity_query="logos",
        include_fallacies=True,
        narrative_text="Leading experts agree this was foretold.",
    )
    section_titles = [section.title for section in report.sections]
    assert "Stability of the Text" in section_titles[0]
    variant_count = report.meta["variant_count"]
    citation_count = report.meta["citation_count"]
    fallacy_count = report.meta["fallacy_count"]

    assert isinstance(variant_count, int)
    assert isinstance(citation_count, int)
    assert isinstance(fallacy_count, int)

    assert variant_count > 0
    assert citation_count >= 1
    assert fallacy_count >= 0


def test_report_build_skeptical_uses_critical_template() -> None:
    service = _research_service()
    report = service.report_build("John.1.1", stance="skeptical")

    assert (
        report.summary
        == "Critical briefing for John.1.1: surface tensions, disputed readings, and historiographical cautions."
    )

    section_titles = {section.title for section in report.sections}
    assert {
        "Disputed Readings",
        "Critical References",
        "Contested Claims",
    }.issubset(section_titles)
