from __future__ import annotations

from theo.domain.research import fetch_passage


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
