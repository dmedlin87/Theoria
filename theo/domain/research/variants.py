"""Helpers for retrieving textual variant apparatus entries."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .datasets import variants_dataset


@dataclass(frozen=True, slots=True)
class VariantEntry:
    id: str
    osis: str
    category: str
    reading: str
    note: str | None = None
    source: str | None = None
    witness: str | None = None
    translation: str | None = None
    confidence: float | None = None
    dataset: str | None = None
    disputed: bool | None = None
    witness_metadata: dict[str, object] | None = None


def _parse_reference(
    reference: str,
    *,
    default_book: str | None = None,
    default_chapter: int | None = None,
) -> tuple[str, int | None, int | None]:
    """Return ``(book, chapter, verse)`` for an OSIS reference fragment."""

    parts = reference.split(".")
    if len(parts) == 1:
        if default_book is None:
            raise ValueError(f"Cannot infer book for OSIS reference '{reference}'")
        try:
            verse = int(parts[0])
        except ValueError as exc:  # pragma: no cover - defensive validation
            raise ValueError(f"Invalid OSIS verse '{parts[0]}'") from exc
        return default_book, default_chapter, verse

    if len(parts) == 2:
        first, second = parts
        try:
            second_int = int(second)
        except ValueError as exc:  # pragma: no cover - defensive validation
            raise ValueError(f"Invalid OSIS component '{second}'") from exc

        try:
            first_int = int(first)
        except ValueError:
            # Treat as "Book.Chapter" (no verse provided)
            return first, second_int, None

        if default_book is None:
            # Explicit "Chapter.Verse" without a book reference
            raise ValueError(
                f"Cannot infer book for OSIS reference '{reference}'"
            )
        return default_book, first_int, second_int

    if len(parts) == 3:
        book, chapter, verse = parts
        try:
            chapter_int = int(chapter)
            verse_int = int(verse)
        except ValueError as exc:  # pragma: no cover - defensive validation
            raise ValueError(f"Invalid OSIS reference '{reference}'") from exc
        return book, chapter_int, verse_int

    raise ValueError(f"Unsupported OSIS reference '{reference}'")


def _sort_key(
    *,
    book: str,
    chapter: int | None,
    verse: int | None,
    high: bool,
) -> tuple[str, int, int]:
    """Return a tuple suitable for lexicographic comparisons."""

    chapter_value = chapter if chapter is not None else (9999 if high else -1)
    verse_value = verse if verse is not None else (9999 if high else -1)
    return book, chapter_value, verse_value


def _expand_osis(
    osis: str,
    dataset: Mapping[str, Iterable[dict[str, object]]] | None = None,
) -> list[str]:
    """Expand a verse or range into individual OSIS keys, honoring chapter spans."""

    if dataset is None:
        dataset = variants_dataset()

    if "-" not in osis:
        return [osis]

    start_raw, end_raw = osis.split("-", 1)
    start_book, start_chapter, start_verse = _parse_reference(start_raw)
    end_book, end_chapter, end_verse = _parse_reference(
        end_raw,
        default_book=start_book,
        default_chapter=start_chapter,
    )

    start_data = {
        "book": start_book,
        "chapter": start_chapter,
        "verse": start_verse,
    }
    end_data = {
        "book": end_book,
        "chapter": end_chapter,
        "verse": end_verse,
    }

    start_key = _sort_key(
        book=start_book, chapter=start_chapter, verse=start_verse, high=False
    )
    end_key = _sort_key(book=end_book, chapter=end_chapter, verse=end_verse, high=True)

    if start_key > end_key:
        start_data, end_data = end_data, start_data
        start_key = _sort_key(
            book=start_data["book"],
            chapter=start_data["chapter"],
            verse=start_data["verse"],
            high=False,
        )
        end_key = _sort_key(
            book=end_data["book"],
            chapter=end_data["chapter"],
            verse=end_data["verse"],
            high=True,
        )

    matched: dict[str, tuple[str, int, int]] = {}
    for key in dataset.keys():
        try:
            book, chapter, verse = _parse_reference(key)
        except ValueError:
            continue
        sort_key = _sort_key(book=book, chapter=chapter, verse=verse, high=False)
        if start_key <= sort_key <= end_key:
            matched.setdefault(key, sort_key)

    if (
        start_data["book"] == end_data["book"]
        and start_data["chapter"] is not None
        and start_data["chapter"] == end_data["chapter"]
        and start_data["verse"] is not None
        and end_data["verse"] is not None
    ):
        for verse in range(start_data["verse"], end_data["verse"] + 1):
            key = f"{start_data['book']}.{start_data['chapter']}.{verse}"
            sort_key = _sort_key(
                book=start_data["book"],
                chapter=start_data["chapter"],
                verse=verse,
                high=False,
            )
            if start_key <= sort_key <= end_key:
                matched.setdefault(key, sort_key)

    return [key for key, _ in sorted(matched.items(), key=lambda item: item[1])]


def variants_apparatus(
    osis: str,
    *,
    categories: Iterable[str] | None = None,
    limit: int | None = None,
) -> list[VariantEntry]:
    """Return apparatus entries for the supplied reference."""

    normalized_categories = {c.lower() for c in categories or []} or None
    dataset = variants_dataset()
    osis_keys = _expand_osis(osis, dataset)

    entries: list[VariantEntry] = []
    for key in osis_keys:
        for raw in dataset.get(key, []):
            category = raw.get("category", "note")
            if normalized_categories and category.lower() not in normalized_categories:
                continue
            entries.append(
                VariantEntry(
                    id=raw["id"],
                    osis=key,
                    category=category,
                    reading=raw["reading"],
                    note=raw.get("note"),
                    source=raw.get("source"),
                    witness=raw.get("witness"),
                    translation=raw.get("translation"),
                    confidence=raw.get("confidence"),
                    dataset=raw.get("dataset"),
                    disputed=raw.get("disputed"),
                    witness_metadata=raw.get("witness_metadata"),
                )
            )

    if limit is not None:
        entries = entries[:limit]

    return entries


__all__ = ["VariantEntry", "variants_apparatus"]
