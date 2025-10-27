from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List

from theo.adapters.biblical_ai_processor import BiblicalAIProcessor
from theo.domain.biblical_texts import (
    BibleVersion,
    BiblicalBook,
    Language,
    Reference,
    TheologicalTermTracker,
)

from tests.integration._stubs import install_sklearn_stub

install_sklearn_stub()


@dataclass
class _StubMessage:
    content: str


@dataclass
class _StubChoice:
    message: _StubMessage


@dataclass
class _StubResponse:
    choices: List[_StubChoice]


class _FakeCompletions:
    def __init__(self, payloads: list[str]) -> None:
        self._payloads = list(payloads)

    def create(self, *_, **__) -> _StubResponse:
        if not self._payloads:
            raise AssertionError("No payloads remaining for fake AI client")
        content = self._payloads.pop(0)
        return _StubResponse([_StubChoice(_StubMessage(content))])


class _FakeChat:
    def __init__(self, payloads: list[str]) -> None:
        self.completions = _FakeCompletions(payloads)


class _FakeAIClient:
    def __init__(self, payloads: list[str]) -> None:
        self.chat = _FakeChat(payloads)


def test_biblical_analysis_workflow_end_to_end() -> None:
    """Validate ingestion, AI analysis, and search over biblical content."""

    morphology_payload = json.dumps(
        [
            {
                "word": "???????????",
                "lemma": "????????",
                "root": "???",
                "pos": "noun",
                "gender": "feminine",
                "number": "singular",
                "state": "construct",
                "gloss": "beginning",
                "theological_notes": ["creation_narrative"],
            },
            {
                "word": "??????",
                "lemma": "???",
                "root": "???",
                "pos": "verb",
                "stem": "qal",
                "tense": "perfect",
                "person": 3,
                "gender": "masculine",
                "number": "singular",
                "gloss": "create",
                "theological_notes": ["divine_creation"],
            },
            {
                "word": "????????",
                "lemma": "?????",
                "root": "???",
                "pos": "noun",
                "gender": "masculine",
                "number": "plural",
                "state": "absolute",
                "gloss": "God",
                "theological_notes": ["divine_name", "plural_form_singular_verb"],
            },
        ]
    )
    semantic_payload = json.dumps(
        {
            "themes": ["creation", "cosmology"],
            "theological_keywords": ["?????", "???"],
            "cross_references": ["John.1.1"],
            "textual_variants": [],
            "translation_notes": {
                "plural": "Plural noun with singular verb emphasises divine unity",
            },
        }
    )
    processor = BiblicalAIProcessor(
        _FakeAIClient(
            [
                "Bereshit bara Elohim et hashamayim ve'et haaretz",
                morphology_payload,
                semantic_payload,
            ]
        )
    )
    reference = Reference(
        book="Genesis",
        chapter=1,
        verse=1,
        book_id="gen",
        osis_id="Gen.1.1",
    )
    verse = processor.process_hebrew_verse(
        "??????????? ?????? ???????? ??? ??????????? ????? ???????",
        reference,
    )

    assert verse.language is Language.HEBREW
    assert verse.semantic_analysis is not None
    assert "creation" in verse.semantic_analysis.themes

    book = BiblicalBook(
        id="gen",
        name="Genesis",
        native_name="??????",
        language=Language.HEBREW,
        chapter_count=50,
        verses={"1:1": verse},
    )
    version = BibleVersion(
        name="WLC",
        abbreviation="WLC",
        language=Language.HEBREW,
        license="public-domain",
        source_url=None,
        version="1.0",
        description="Sample dataset",
        books={"gen": book},
    )

    matches = book.search_word("?????", lemma=True)
    assert matches == [verse]

    divine_occurrences = TheologicalTermTracker.find_elohim_singular_verbs(version)
    assert len(divine_occurrences) == 1
    assert divine_occurrences[0].reference.osis_id == "Gen.1.1"
