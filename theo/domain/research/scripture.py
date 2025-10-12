"""Scripture dataset helpers."""
from __future__ import annotations

from dataclasses import dataclass

from .datasets import scripture_dataset


@dataclass(frozen=True, slots=True)
class Verse:
    osis: str
    translation: str
    text: str
    book: str | None = None
    chapter: int | None = None
    verse: int | None = None


def _normalize_translation(translation: str | None) -> str:
    return (translation or "SBLGNT").upper()


def fetch_passage(osis: str, translation: str | None = None) -> list[Verse]:
    """Return a list of verses for the requested OSIS reference."""

    translation_key = _normalize_translation(translation)
    translations = scripture_dataset()
    try:
        verses_by_osis = translations[translation_key]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise KeyError(f"Unknown translation '{translation_key}'") from exc

    if "." not in osis:
        raise ValueError("OSIS references must include book and chapter segments")

    if "-" not in osis:
        verse_keys = [osis]
    else:
        start, end = osis.split("-", 1)
        if "." not in end:
            end = f"{start.rsplit('.', 1)[0]}.{end}"
        book_chapter = start.rsplit(".", 1)[0]
        start_verse = int(start.split(".")[-1])
        end_verse = int(end.split(".")[-1])
        verse_keys = [
            f"{book_chapter}.{idx}" for idx in range(start_verse, end_verse + 1)
        ]

    verses: list[Verse] = []
    for key in verse_keys:
        entry = verses_by_osis.get(key)
        if not entry:
            continue
        verses.append(
            Verse(
                osis=key,
                translation=translation_key,
                text=entry["text"],
                book=entry.get("book"),
                chapter=entry.get("chapter"),
                verse=entry.get("verse"),
            )
        )
    if not verses:
        raise KeyError(f"No scripture data available for '{osis}'")
    return verses


__all__ = ["Verse", "fetch_passage"]
