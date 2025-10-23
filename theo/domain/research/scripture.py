"""Scripture dataset helpers."""
from __future__ import annotations

from dataclasses import dataclass

import pythonbible as pb

from .datasets import scripture_dataset
from .osis import expand_osis_reference, verse_ids_to_osis


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

    verse_keys = _expand_osis_to_keys(osis)
    if not verse_keys:
        verse_keys = [osis]

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


def _expand_osis_to_keys(osis: str) -> list[str]:
    """Expand *osis* into individual verse keys in canonical order."""

    verse_ids = expand_osis_reference(osis)
    if not verse_ids and "-" in osis:
        start, end = osis.split("-", 1)
        start_ids = expand_osis_reference(start)
        end_ids = expand_osis_reference(end)
        if start_ids and end_ids:
            lower = min(min(start_ids), min(end_ids))
            upper = max(max(start_ids), max(end_ids))
            verse_ids = frozenset(
                verse_id
                for verse_id in range(lower, upper + 1)
                if pb.is_valid_verse_id(verse_id)
            )
    if not verse_ids:
        return []

    sorted_ids = sorted(set(verse_ids))
    return list(verse_ids_to_osis(sorted_ids))


__all__ = ["Verse", "fetch_passage"]
