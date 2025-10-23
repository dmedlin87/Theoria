from __future__ import annotations

import pytest

from theo.domain.research import fetch_passage
from theo.domain.research import scripture as scripture_module


def test_expand_osis_to_keys_handles_manual_ranges(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ranges falling back to manual expansion should preserve ordering."""

    def fake_expand(reference: str) -> frozenset[int]:
        if reference == "John.1.1":
            return frozenset({1})
        if reference == "John.1.3":
            return frozenset({3})
        return frozenset()

    monkeypatch.setattr(scripture_module, "expand_osis_reference", fake_expand)
    monkeypatch.setattr(
        scripture_module,
        "verse_ids_to_osis",
        lambda ids: [f"Verse-{value}" for value in ids],
    )
    monkeypatch.setattr(
        scripture_module.pb,
        "is_valid_verse_id",
        lambda verse_id: verse_id in {1, 2, 3},
    )

    result = scripture_module._expand_osis_to_keys("John.1.1-John.1.3")

    assert result == ["Verse-1", "Verse-2", "Verse-3"]


def test_fetch_passage_cross_chapter_range() -> None:
    verses = fetch_passage("John.1.50-John.2.2")

    assert [verse.osis for verse in verses] == [
        "John.1.50",
        "John.1.51",
        "John.2.1",
        "John.2.2",
    ]
    assert {verse.translation for verse in verses} == {"SBLGNT"}


def test_fetch_passage_handles_reversed_bounds() -> None:
    verses = fetch_passage("John.2.2-John.1.50")

    assert [verse.osis for verse in verses] == [
        "John.1.50",
        "John.1.51",
        "John.2.1",
        "John.2.2",
    ]


def test_fetch_passage_normalizes_translation(monkeypatch: pytest.MonkeyPatch) -> None:
    verses_by_translation = {
        "SBLGNT": {
            "John.3.16": {
                "text": "For God so loved the world",
                "book": "John",
                "chapter": 3,
                "verse": 16,
            }
        }
    }
    monkeypatch.setattr(
        scripture_module,
        "scripture_dataset",
        lambda: verses_by_translation,
    )

    verses = fetch_passage("John.3.16", translation="sblgnt")

    assert [verse.translation for verse in verses] == ["SBLGNT"]


def test_fetch_passage_rejects_incomplete_reference() -> None:
    with pytest.raises(ValueError):
        fetch_passage("John3")


def test_fetch_passage_raises_for_unknown_translation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        scripture_module,
        "scripture_dataset",
        lambda: {"SBLGNT": {}},
    )

    with pytest.raises(KeyError, match="Unknown translation 'KJV'"):
        fetch_passage("John.1.1", translation="kjv")


def test_fetch_passage_raises_when_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        scripture_module,
        "scripture_dataset",
        lambda: {"SBLGNT": {}},
    )

    with pytest.raises(KeyError, match="No scripture data available for 'John.3.16'"):
        fetch_passage("John.3.16")
