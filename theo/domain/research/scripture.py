"""Scripture dataset helpers."""
from __future__ import annotations

from dataclasses import dataclass

try:  # pragma: no cover - optional dependency in lightweight tests
    import pythonbible as pb
except ModuleNotFoundError:  # pragma: no cover - provide basic fallback helpers
    class _PythonBibleStub:
        @staticmethod
        def is_valid_verse_id(_verse_id: int) -> bool:
            return True

    pb = _PythonBibleStub()  # type: ignore[assignment]

from collections.abc import Mapping

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

    verse_keys = _expand_osis_to_keys(osis, verses_by_osis)
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


def _expand_osis_to_keys(
    osis: str, verses_by_osis: Mapping[str, Mapping[str, object]] | None = None
) -> list[str]:
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
        elif verses_by_osis is not None:
            fallback_keys = _fallback_expand_osis_by_dataset(osis, verses_by_osis)
            if fallback_keys:
                return fallback_keys
    if not verse_ids:
        return []

    sorted_ids = sorted(set(verse_ids))
    return list(verse_ids_to_osis(sorted_ids))


def _fallback_expand_osis_by_dataset(
    osis: str, verses_by_osis: Mapping[str, Mapping[str, object]]
) -> list[str]:
    """Fallback when pythonbible is unavailable by slicing the dataset order."""

    if "-" not in osis:
        return []

    start, end = osis.split("-", 1)
    keys = list(verses_by_osis.keys())
    try:
        start_index = keys.index(start)
        end_index = keys.index(end)
    except ValueError:
        return []

    lower = min(start_index, end_index)
    upper = max(start_index, end_index)
    return keys[lower : upper + 1]


__all__ = ["Verse", "fetch_passage"]
