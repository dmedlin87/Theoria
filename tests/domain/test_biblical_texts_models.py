"""Unit tests for domain models in :mod:`theo.domain.biblical_texts`."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from theo.domain.biblical_texts import (
    AIAnalysis,
    BiblicalBook,
    BiblicalVerse,
    BibleVersion,
    Language,
    ManuscriptData,
    MorphologicalTag,
    POS,
    Reference,
    SemanticAnalysis,
    TextContent,
    TheologicalTermTracker,
)


@pytest.fixture
def sample_reference() -> Reference:
    return Reference("Genesis", 1, 1, "gen", "Gen.1.1")


@pytest.fixture
def sample_text() -> TextContent:
    return TextContent(
        raw="בראשית ברא אלהים את השמים ואת הארץ",
        normalized="בראשית ברא אלהים את השמים ואת הארץ",
        transliteration="bereshit bara elohim et hashamayim ve'et ha'aretz",
    )


@pytest.fixture
def sample_semantics() -> SemanticAnalysis:
    return SemanticAnalysis(
        themes=["creation"],
        theological_keywords=["creation", "divine_power"],
        cross_references=["John.1.1"],
        textual_variants=["variant_a"],
        translation_notes={"KJV": "In the beginning"},
    )


@pytest.fixture
def sample_morphology() -> list[MorphologicalTag]:
    return [
        MorphologicalTag(
            word="בראשית",
            lemma="ראשית",
            root="ראש",
            pos=POS.NOUN,
            gender="feminine",
            number="singular",
            gloss="beginning",
            theological_notes=["creation"],
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


@pytest.fixture
def sample_verse(
    sample_reference: Reference,
    sample_text: TextContent,
    sample_morphology: list[MorphologicalTag],
    sample_semantics: SemanticAnalysis,
) -> BiblicalVerse:
    return BiblicalVerse(
        reference=sample_reference,
        language=Language.HEBREW,
        text=sample_text,
        morphology=sample_morphology,
        semantic_analysis=sample_semantics,
        manuscript_data=ManuscriptData(source="WLC", variants=["variant_a"]),
        ai_analysis=AIAnalysis(
            generated_at=datetime(2023, 1, 1),
            model_version="1.0",
            confidence_scores={"creation": 0.95},
        ),
    )


def test_reference_behaves_as_value_object(sample_reference: Reference) -> None:
    assert str(sample_reference) == "Genesis 1:1"
    assert sample_reference == Reference("Genesis", 1, 1, "gen", "Gen.1.1")

    with pytest.raises(FrozenInstanceError):
        sample_reference.book = "Exodus"  # type: ignore[misc]


def test_biblical_verse_word_and_keyword_extraction(sample_verse: BiblicalVerse) -> None:
    assert sample_verse.get_words() == ["בראשית", "ברא", "אלהים"]

    keywords = sample_verse.get_theological_keywords()
    assert set(keywords) == {"בראשית", "creation", "divine_power"}


def test_find_divine_names_includes_roots_and_notes(
    sample_verse: BiblicalVerse, sample_morphology: list[MorphologicalTag]
) -> None:
    enriched_tags = list(sample_morphology)
    enriched_tags.append(
        MorphologicalTag(
            word="אדני",
            lemma="אדני",
            root="אדן",
            pos=POS.NOUN,
            theological_notes=["divine_name"],
        )
    )
    verse = sample_verse.__class__(
        reference=sample_verse.reference,
        language=sample_verse.language,
        text=sample_verse.text,
        morphology=enriched_tags,
        semantic_analysis=sample_verse.semantic_analysis,
        manuscript_data=sample_verse.manuscript_data,
        ai_analysis=sample_verse.ai_analysis,
    )

    divine_tags = verse.find_divine_names()
    assert {tag.word for tag in divine_tags} == {"אלהים", "אדני"}


def test_biblical_book_and_version_navigation(sample_verse: BiblicalVerse) -> None:
    book = BiblicalBook(
        id="gen",
        name="Genesis",
        native_name="בראשית",
        language=Language.HEBREW,
        chapter_count=50,
        verses={"1:1": sample_verse},
    )
    version = BibleVersion(
        name="Westminster Leningrad Codex",
        abbreviation="WLC",
        language=Language.HEBREW,
        license="Public Domain",
        source_url=None,
        version="1.0",
        description="Test version",
        features=["morphology"],
        books={"gen": book},
    )

    assert book.get_verse(1, 1) == sample_verse
    assert book.get_verse(1, 2) is None
    assert version.get_book("gen") is book
    assert version.get_verse(sample_verse.reference) == sample_verse
    assert version.get_verse(Reference("Exodus", 1, 1, "exo", "Exod.1.1")) is None


def test_book_search_supports_word_and_lemma(sample_verse: BiblicalVerse) -> None:
    book = BiblicalBook(
        id="gen",
        name="Genesis",
        native_name=None,
        language=Language.HEBREW,
        chapter_count=50,
        verses={"1:1": sample_verse},
    )

    results_word = book.search_word("ברא")
    results_lemma = book.search_word("ברא", lemma=True)

    assert results_word == [sample_verse]
    assert results_lemma == [sample_verse]


def test_theological_term_tracker_finds_singular_verbs(
    sample_verse: BiblicalVerse,
) -> None:
    book = BiblicalBook(
        id="gen",
        name="Genesis",
        native_name=None,
        language=Language.HEBREW,
        chapter_count=1,
        verses={"1:1": sample_verse},
    )
    version = BibleVersion(
        name="Test",
        abbreviation="TST",
        language=Language.HEBREW,
        license="",
        source_url=None,
        version="0",
        description="",
        books={"gen": book},
    )

    matches = TheologicalTermTracker.find_elohim_singular_verbs(version)

    assert matches == [sample_verse]


def test_theological_term_tracker_compare_returns_expected_structure(sample_verse: BiblicalVerse) -> None:
    comparison = TheologicalTermTracker.compare_hebrew_lxx_terms(
        sample_verse,
        sample_verse,
        term="ברא",
    )

    assert comparison == {
        "hebrew_forms": ["ברא"],
        "lxx_renderings": [],
        "semantic_shift_notes": [],
    }


def test_biblical_verse_immutability(sample_verse: BiblicalVerse) -> None:
    with pytest.raises(FrozenInstanceError):
        sample_verse.language = Language.GREEK  # type: ignore[misc]

