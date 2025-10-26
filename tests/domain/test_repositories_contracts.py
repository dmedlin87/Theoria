"""Tests for domain repository contracts and services."""
from __future__ import annotations

import pytest

from theo.domain.biblical_texts import (
    BiblicalVerse,
    Language,
    MorphologicalTag,
    POS,
    Reference,
    SemanticAnalysis,
    TextContent,
)
from theo.domain.repositories.biblical_texts import (
    BiblicalTextRepository,
    CrossTranslationAnalyzer,
    TheologicalResearchRepository,
)


def make_sample_verse(osis: str) -> BiblicalVerse:
    reference = Reference("Genesis", 1, 1, "gen", osis)
    text = TextContent(raw="בראשית ברא אלהים", normalized="בראשית ברא אלהים")
    morphology = [
        MorphologicalTag(
            word="בראשית",
            lemma="ראשית",
            root="ראש",
            pos=POS.NOUN,
            gloss="beginning",
        ),
        MorphologicalTag(
            word="ברא",
            lemma="ברא",
            root="ברא",
            pos=POS.VERB,
            number="singular",
            person=3,
            gloss="create",
        ),
        MorphologicalTag(
            word="אלהים",
            lemma="אלהים",
            root="אלה",
            pos=POS.NOUN,
            number="plural",
            gloss="God",
        ),
    ]
    semantics = SemanticAnalysis(
        themes=["creation"],
        theological_keywords=[],
        cross_references=[],
        textual_variants=[],
    )

    return BiblicalVerse(
        reference=reference,
        language=Language.HEBREW,
        text=text,
        morphology=morphology,
        semantic_analysis=semantics,
        manuscript_data=None,
        ai_analysis=None,
    )


class FakeBiblicalRepository(BiblicalTextRepository):
    def __init__(self) -> None:
        self.verses: dict[tuple[str, str], BiblicalVerse] = {}
        self.search_by_word_calls: list[tuple[str, str, bool, tuple[str, ...] | None]] = []
        self.search_theological_terms_calls: list[tuple[tuple[str, ...], str]] = []

    def get_version(self, abbreviation: str):  # pragma: no cover - not exercised
        return None

    def get_verse(self, reference: Reference, version: str = "WLC"):
        return self.verses.get((reference.osis_id, version))

    def get_parallel_verses(self, reference: Reference, versions: list[str]):  # pragma: no cover
        return {}

    def search_by_word(
        self,
        word: str,
        version: str = "WLC",
        lemma: bool = False,
        books: list[str] | None = None,
    ):
        call = (word, version, lemma, tuple(books) if books else None)
        self.search_by_word_calls.append(call)
        return [make_sample_verse("Gen.1.1")]

    def search_by_root(self, root: str, version: str = "WLC"):  # pragma: no cover
        return []

    def search_theological_terms(
        self, terms: list[str], version: str = "WLC"
    ):
        self.search_theological_terms_calls.append((tuple(terms), version))
        return {term: [make_sample_verse("Gen.1.1")] for term in terms}


class FakeResearchRepository(TheologicalResearchRepository):
    def __init__(self) -> None:
        self.compare_calls: list[str] = []
        self.find_divine_calls: list[str] = []

    def find_divine_name_patterns(self, version: str = "WLC"):
        self.find_divine_calls.append(version)
        return {"יהוה": [make_sample_verse("Gen.1.1")]}

    def analyze_elohim_verb_agreement(self, version: str = "WLC"):
        return {"matches": [make_sample_verse("Gen.1.1")]}

    def compare_hebrew_lxx_renderings(self, hebrew_term: str):
        self.compare_calls.append(hebrew_term)
        return [{"term": hebrew_term, "renderings": []}]

    def find_christological_passages(self):
        return {"Isa.7.14": (make_sample_verse("Isa.7.14"), make_sample_verse("Isa.7.14"))}

    def track_messianic_terminology(self):  # pragma: no cover
        return {}

    def analyze_textual_variants(self, reference: Reference):  # pragma: no cover
        return {}

def test_repository_interfaces_are_abstract():
    with pytest.raises(TypeError):
        BiblicalTextRepository()  # type: ignore[abstract]

    with pytest.raises(TypeError):
        TheologicalResearchRepository()  # type: ignore[abstract]


def test_cross_translation_analyzer_aggregates_research_calls():
    biblical_repo = FakeBiblicalRepository()
    research_repo = FakeResearchRepository()
    analyzer = CrossTranslationAnalyzer(biblical_repo, research_repo)

    results = analyzer.analyze_trinity_evidence()

    assert set(results) == {
        "elohim_singular_verbs",
        "divine_plural_references",
        "christological_passages",
        "lxx_theos_usage",
    }
    assert research_repo.compare_calls[-1] == "אלהים"
    assert research_repo.find_divine_calls == ["WLC"]


def test_divine_name_study_uses_search_and_comparison():
    biblical_repo = FakeBiblicalRepository()
    research_repo = FakeResearchRepository()
    analyzer = CrossTranslationAnalyzer(biblical_repo, research_repo)

    study = analyzer.analyze_divine_names_study()

    assert set(study) == {"יהוה", "אלהים", "אדני", "אל שדי"}
    for call in biblical_repo.search_by_word_calls:
        assert call[2] is True  # lemma search requested
    assert len(research_repo.compare_calls) >= 4


def test_messianic_prophecy_analysis_requires_parallel_verses():
    biblical_repo = FakeBiblicalRepository()
    research_repo = FakeResearchRepository()
    analyzer = CrossTranslationAnalyzer(biblical_repo, research_repo)

    # populate both Hebrew and LXX verses
    for ref in [
        Reference("Isaiah", 7, 14, "isa", "Isa.7.14"),
        Reference("Isaiah", 9, 6, "isa", "Isa.9.6"),
        Reference("Isaiah", 53, 0, "isa", "Isa.53"),
        Reference("Daniel", 9, 25, "dan", "Dan.9.25"),
        Reference("Psalms", 22, 0, "psa", "Ps.22"),
    ]:
        biblical_repo.verses[(ref.osis_id, "WLC")] = make_sample_verse(ref.osis_id)
        biblical_repo.verses[(ref.osis_id, "LXX")] = make_sample_verse(ref.osis_id)

    analysis = analyzer.analyze_messianic_prophecies()

    assert set(analysis) == {"Isa.7.14", "Isa.9.6", "Isa.53", "Dan.9.25", "Ps.22"}
    for details in analysis.values():
        assert set(details) == {"hebrew", "lxx", "comparison", "theological_implications"}


def test_topic_search_returns_empty_for_unknown_topics():
    analyzer = CrossTranslationAnalyzer(FakeBiblicalRepository(), FakeResearchRepository())

    assert analyzer.search_theological_debate_passages("unknown") == {}


def test_topic_search_enriches_results_with_lxx_comparisons():
    biblical_repo = FakeBiblicalRepository()
    research_repo = FakeResearchRepository()
    analyzer = CrossTranslationAnalyzer(biblical_repo, research_repo)

    results = analyzer.search_theological_debate_passages("trinity")

    assert "אלהים" in results
    assert "trinity" not in results  # original terms as keys only
    assert "אלהים_lxx_comparison" in results
    requested_terms = biblical_repo.search_theological_terms_calls[0][0]
    assert set(requested_terms) == {"אלהים", "רוח אלהים", "בן אלהים"}
