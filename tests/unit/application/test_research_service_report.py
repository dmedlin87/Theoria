import pytest

from theo.application.research import service as service_module
from theo.application.research.service import ResearchService
from theo.domain import FallacyHit, HistoricityEntry, VariantEntry


class _DummyNotesRepository:
    """Minimal repository stub for instantiating ``ResearchService``."""
    pass


@pytest.fixture
def service():
    return ResearchService(_DummyNotesRepository())


def test_report_build_uses_templates_and_includes_fallacies(monkeypatch, service):
    variant_entries = [
        VariantEntry(
            id="var-1",
            osis="John.3.16",
            category="manuscript",
            reading="Reading",
            note="Note",
            source="Source",
            witness="W",
            translation="EN",
            confidence=0.9,
        )
    ]
    citation_entries = [
        HistoricityEntry(
            id="hist-1",
            title="Title",
            authors=["Author"],
            year=2020,
            summary="Summary",
            source="Book",
            url="https://example.com",
            tags=["tag"],
            score=1.0,
        )
    ]
    fallacy_hits = [
        FallacyHit(
            id="fallacy-1",
            name="Appeal to Emotion",
            category="Emotion",
            description="Description",
            severity="medium",
            confidence=0.7,
            matches=["emotion"],
        )
    ]

    helper_calls = []
    monkeypatch.setattr(
        service_module,
        "report_templates_dataset",
        lambda: {
            "critical": {
                "summary": "Briefing {osis} - {stance}",
                "sections": {
                    "variants": "Variant Insights",
                    "historicity": "Contextual Sources",
                    "fallacies": "Fallacy Audit",
                    "claims": "Argument Claims",
                },
            }
        },
    )

    def fake_variants(osis: str, *, categories=None, limit=None):
        helper_calls.append(("variants", osis, categories, limit))
        return variant_entries

    def fake_historicity(query: str, *, limit: int, year_from=None, year_to=None):
        helper_calls.append(("historicity", query, limit))
        return citation_entries

    def fake_fallacies(text: str, *, min_confidence: float):
        helper_calls.append(("fallacy", text, min_confidence))
        return fallacy_hits

    monkeypatch.setattr(service_module, "variants_apparatus", fake_variants)
    monkeypatch.setattr(service_module, "historicity_search", fake_historicity)
    monkeypatch.setattr(service_module, "fallacy_detect", fake_fallacies)

    report = service.report_build(
        "John.3.16",
        stance="Skeptical",
        claims=[{"text": "A supplied claim"}],
        include_fallacies=True,
        narrative_text="An argument worth reviewing.",
        variants_limit=5,
        citations_limit=4,
        min_fallacy_confidence=0.25,
    )

    # Ensure external helpers received the normalized arguments.
    assert ("variants", "John.3.16", None, 5) in helper_calls
    assert ("historicity", "John.3.16", 4) in helper_calls
    assert ("fallacy", "An argument worth reviewing.", 0.25) in helper_calls

    assert report.summary == "Briefing John.3.16 - Skeptical"
    assert [section.title for section in report.sections] == [
        "Variant Insights",
        "Contextual Sources",
        "Fallacy Audit",
        "Argument Claims",
    ]
    fallacy_section = report.sections[2]
    assert fallacy_section.summary.startswith("Potential rhetorical weaknesses")
    assert fallacy_section.items == [
        {
            "id": "fallacy-1",
            "name": "Appeal to Emotion",
            "category": "Emotion",
            "description": "Description",
            "severity": "medium",
            "confidence": 0.7,
            "matches": ["emotion"],
        }
    ]
    assert report.meta == {
        "variant_count": 1,
        "citation_count": 1,
        "fallacy_count": 1,
    }


def test_report_build_skips_fallacy_detection_without_narrative(monkeypatch, service):
    monkeypatch.setattr(service_module, "variants_apparatus", lambda *_, **__: [])

    def fake_historicity(query: str, *, limit: int, year_from=None, year_to=None):
        assert query == "John.3.16"
        assert limit == 5
        return []

    monkeypatch.setattr(service_module, "historicity_search", fake_historicity)
    monkeypatch.setattr(service_module, "report_templates_dataset", lambda: {})
    monkeypatch.setattr(
        service_module,
        "fallacy_detect",
        lambda *_, **__: pytest.fail("fallacy detection should not run"),
    )

    report = service.report_build(
        "John.3.16",
        stance="Affirming",
        include_fallacies=True,
        narrative_text=None,
    )

    assert report.summary == "Research briefing for John.3.16 (Affirming)."
    assert [section.title for section in report.sections] == [
        "Textual Variants",
        "Historicity Sources",
        "Fallacy Audit",
        "Key Claims",
    ]
    fallacy_section = report.sections[2]
    assert fallacy_section.summary == "No fallacy audit requested."
    assert fallacy_section.items == []
    assert report.meta["fallacy_count"] == 0
