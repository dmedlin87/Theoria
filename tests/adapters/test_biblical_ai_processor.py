from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from theo.adapters.biblical_ai_processor import BiblicalAIProcessor
from theo.domain.biblical_texts import Language, POS, Reference


@dataclass
class _RecordedCall:
    model: str
    prompt: str
    temperature: float


@dataclass
class _StubCompletions:
    responses: list[str]
    calls: list[_RecordedCall] = field(default_factory=list)

    def create(self, *, model: str, messages, temperature: float) -> SimpleNamespace:  # noqa: ANN001 - test stub signature
        prompt = messages[0]["content"]
        self.calls.append(_RecordedCall(model=model, prompt=prompt, temperature=temperature))
        try:
            content = self.responses.pop(0)
        except IndexError:  # pragma: no cover - defensive guard for misconfigured test
            raise AssertionError("No stubbed responses remaining for AI client call")
        choice = SimpleNamespace(message=SimpleNamespace(content=content))
        return SimpleNamespace(choices=[choice])


@dataclass
class _StubChat:
    completions: _StubCompletions


@dataclass
class _StubAIClient:
    completions: _StubCompletions

    def __post_init__(self) -> None:
        self.chat = _StubChat(self.completions)


@pytest.fixture()
def reference() -> Reference:
    return Reference(book="Genesis", chapter=1, verse=1, book_id="GEN", osis_id="Gen.1.1")


def test_process_hebrew_verse_returns_structured_analysis(reference: Reference) -> None:
    completions = _StubCompletions(
        responses=[
            "bereshit bara",
            '[{"word": "בְּרֵאשִׁית", "lemma": "בְּרֵאשִׁית", "root": "ראש", "pos": "noun", "gloss": "beginning", "theological_notes": ["creation"]}]',
            '{"themes": ["Creation"], "theological_keywords": ["creation"], "cross_references": ["John 1:1"], "textual_variants": [], "translation_notes": {"note": "God created"}}',
        ]
    )
    processor = BiblicalAIProcessor(_StubAIClient(completions), model_name="gpt-test")

    verse = processor.process_hebrew_verse("בְּרֵאשִׁית", reference)

    assert verse.reference == reference
    assert verse.language is Language.HEBREW
    assert verse.text.raw == "בְּרֵאשִׁית"
    assert verse.text.normalized == "בראשית"
    assert verse.text.transliteration == "bereshit bara"
    assert verse.ai_analysis is not None
    assert verse.ai_analysis.model_version == "gpt-test"

    assert len(verse.morphology) == 1
    tag = verse.morphology[0]
    assert tag.word == "בְּרֵאשִׁית"
    assert tag.pos is POS.NOUN
    assert tag.theological_notes == ["creation"]

    assert verse.semantic_analysis is not None
    assert verse.semantic_analysis.themes == ["Creation"]
    assert verse.semantic_analysis.cross_references == ["John 1:1"]

    # Ensure prompts were sent to the AI client in the expected order
    assert [call.model for call in completions.calls] == ["gpt-test", "gpt-test", "gpt-test"]
    assert "Transliterate this Hebrew text" in completions.calls[0].prompt
    assert "Perform morphological analysis" in completions.calls[1].prompt
    assert "Analyze this biblical verse" in completions.calls[2].prompt


def test_process_hebrew_verse_handles_invalid_ai_payloads(reference: Reference) -> None:
    completions = _StubCompletions(
        responses=[
            "qal start",
            "not-json",
            "{\"themes\": [1, 2, 3]}",
        ]
    )
    processor = BiblicalAIProcessor(_StubAIClient(completions), model_name="gpt-test")

    verse = processor.process_hebrew_verse("בְּרֵאשִׁית", reference)

    assert verse.text.transliteration == "qal start"
    assert verse.morphology == []
    assert verse.semantic_analysis is not None
    assert verse.semantic_analysis.themes == []
    assert verse.semantic_analysis.theological_keywords == []
