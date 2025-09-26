"""Utilities for detecting and formatting OSIS scripture references."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Sequence

import pythonbible as pb
from pythonbible import Book, NormalizedReference

OSIS_BOOK_NAMES: dict[Book, str] = {
    Book.GENESIS: "Gen",
    Book.EXODUS: "Exod",
    Book.LEVITICUS: "Lev",
    Book.NUMBERS: "Num",
    Book.DEUTERONOMY: "Deut",
    Book.JOSHUA: "Josh",
    Book.JUDGES: "Judg",
    Book.RUTH: "Ruth",
    Book.SAMUEL_1: "1Sam",
    Book.SAMUEL_2: "2Sam",
    Book.KINGS_1: "1Kgs",
    Book.KINGS_2: "2Kgs",
    Book.CHRONICLES_1: "1Chr",
    Book.CHRONICLES_2: "2Chr",
    Book.EZRA: "Ezra",
    Book.NEHEMIAH: "Neh",
    Book.ESTHER: "Esth",
    Book.JOB: "Job",
    Book.PSALMS: "Ps",
    Book.PROVERBS: "Prov",
    Book.ECCLESIASTES: "Eccl",
    Book.SONG_OF_SONGS: "Song",
    Book.ISAIAH: "Isa",
    Book.JEREMIAH: "Jer",
    Book.LAMENTATIONS: "Lam",
    Book.EZEKIEL: "Ezek",
    Book.DANIEL: "Dan",
    Book.HOSEA: "Hos",
    Book.JOEL: "Joel",
    Book.AMOS: "Amos",
    Book.OBADIAH: "Obad",
    Book.JONAH: "Jonah",
    Book.MICAH: "Mic",
    Book.NAHUM: "Nah",
    Book.HABAKKUK: "Hab",
    Book.ZEPHANIAH: "Zeph",
    Book.HAGGAI: "Hag",
    Book.ZECHARIAH: "Zech",
    Book.MALACHI: "Mal",
    Book.MATTHEW: "Matt",
    Book.MARK: "Mark",
    Book.LUKE: "Luke",
    Book.JOHN: "John",
    Book.ACTS: "Acts",
    Book.ROMANS: "Rom",
    Book.CORINTHIANS_1: "1Cor",
    Book.CORINTHIANS_2: "2Cor",
    Book.GALATIANS: "Gal",
    Book.EPHESIANS: "Eph",
    Book.PHILIPPIANS: "Phil",
    Book.COLOSSIANS: "Col",
    Book.THESSALONIANS_1: "1Thess",
    Book.THESSALONIANS_2: "2Thess",
    Book.TIMOTHY_1: "1Tim",
    Book.TIMOTHY_2: "2Tim",
    Book.TITUS: "Titus",
    Book.PHILEMON: "Phlm",
    Book.HEBREWS: "Heb",
    Book.JAMES: "Jas",
    Book.PETER_1: "1Pet",
    Book.PETER_2: "2Pet",
    Book.JOHN_1: "1John",
    Book.JOHN_2: "2John",
    Book.JOHN_3: "3John",
    Book.JUDE: "Jude",
    Book.REVELATION: "Rev",
    Book.TOBIT: "Tob",
    Book.WISDOM_OF_SOLOMON: "Wis",
    Book.ECCLESIASTICUS: "Sir",
    Book.ESDRAS_1: "1Esd",
    Book.MACCABEES_1: "1Macc",
    Book.MACCABEES_2: "2Macc",
}

KNOWN_BOOK_CODES: set[str] = {
    *(OSIS_BOOK_NAMES.values()),
    *(
        book.name.title().replace("_", "")
        for book in pb.Book
        if book not in OSIS_BOOK_NAMES
    ),
}


@dataclass
class DetectedOsis:
    """Detected references for a block of text."""

    primary: str | None
    all: list[str]


def format_osis(reference: NormalizedReference) -> str:
    """Format a pythonbible NormalizedReference into OSIS notation."""

    book_code = OSIS_BOOK_NAMES.get(
        reference.book, reference.book.name.title().replace("_", "")
    )
    start = f"{book_code}.{reference.start_chapter}.{reference.start_verse}"
    same_range = (
        reference.end_chapter == reference.start_chapter
        and reference.end_verse == reference.start_verse
    )
    if same_range:
        return start

    if reference.end_chapter == reference.start_chapter:
        return f"{start}-{reference.end_verse}"

    return f"{start}-{book_code}.{reference.end_chapter}.{reference.end_verse}"


def combine_references(
    references: Sequence[NormalizedReference],
) -> NormalizedReference | None:
    """Return a minimal covering range for contiguous references in the same book."""

    if not references:
        return None

    first_book = references[0].book
    if not all(ref.book == first_book for ref in references):
        return references[0]

    verse_ids: list[int] = []
    for ref in references:
        verse_ids.extend(pb.convert_reference_to_verse_ids(ref))

    if not verse_ids:
        return references[0]

    verse_ids = sorted(set(verse_ids))

    # Only combine references that form one continuous range.
    for previous, current in zip(verse_ids, verse_ids[1:]):
        if current != previous + 1:
            return None
    start_ref = pb.convert_verse_ids_to_references([verse_ids[0]])[0]
    end_ref = pb.convert_verse_ids_to_references([verse_ids[-1]])[0]
    return NormalizedReference(
        book=first_book,
        start_chapter=start_ref.start_chapter,
        start_verse=start_ref.start_verse,
        end_chapter=end_ref.end_chapter,
        end_verse=end_ref.end_verse,
        end_book=None,
    )


def detect_osis_references(text: str) -> DetectedOsis:
    """Detect OSIS references in arbitrary text."""

    normalized = pb.get_references(text)
    if not normalized:
        return DetectedOsis(primary=None, all=[])

    all_refs = [format_osis(ref) for ref in normalized]
    primary_ref = combine_references(normalized)
    primary = format_osis(primary_ref) if primary_ref else all_refs[0]
    return DetectedOsis(primary=primary, all=all_refs)


def _osis_to_readable(reference: str) -> str:
    """Convert an OSIS string into a pythonbible-friendly textual form."""

    start, *rest = reference.split("-")
    start_parts = [part for part in start.split(".") if part]
    if not start_parts:
        raise ValueError("Invalid OSIS reference")

    book = start_parts[0]
    chapter = start_parts[1] if len(start_parts) > 1 else None
    verse = start_parts[2] if len(start_parts) > 2 else None

    if chapter is None:
        text_value = book
    elif verse is None:
        text_value = f"{book} {chapter}"
    else:
        text_value = f"{book} {chapter}:{verse}"

    if not rest:
        return text_value

    end = rest[0]
    end_parts = [part for part in end.split(".") if part]
    if not end_parts:
        return text_value

    def _format_range_end(
        end_book: str | None, end_chapter: str | None, end_verse: str | None
    ) -> str:
        target_book = end_book or book
        if end_chapter is None:
            return f"{text_value}-{target_book}"
        if end_verse is None:
            if target_book == book and verse is None:
                return f"{text_value}-{end_chapter}"
            return f"{text_value}-{target_book} {end_chapter}"
        if target_book == book:
            return f"{text_value}-{end_chapter}:{end_verse}"
        return f"{text_value}-{target_book} {end_chapter}:{end_verse}"

    if verse is not None:
        if len(end_parts) == 1:
            return f"{text_value}-{end_parts[0]}"
        if len(end_parts) == 2:
            if end_parts[0] in KNOWN_BOOK_CODES:
                return _format_range_end(end_parts[0], end_parts[1], None)
            if chapter is not None and end_parts[0] == chapter:
                return f"{text_value}-{end_parts[1]}"
            return f"{text_value}-{end_parts[0]}:{end_parts[1]}"
        end_book = end_parts[0] if end_parts[0] in KNOWN_BOOK_CODES else book
        offset = 1 if end_book == book else 0
        end_chapter = end_parts[offset] if len(end_parts) > offset else None
        end_verse = end_parts[offset + 1] if len(end_parts) > offset + 1 else None
        return _format_range_end(end_book, end_chapter, end_verse)

    if len(end_parts) == 1:
        return f"{text_value}-{end_parts[0]}"
    if len(end_parts) == 2:
        if end_parts[0] in KNOWN_BOOK_CODES:
            return _format_range_end(end_parts[0], end_parts[1], None)
        return _format_range_end(None, end_parts[0], end_parts[1])

    end_book = end_parts[0] if end_parts[0] in KNOWN_BOOK_CODES else book
    offset = 1 if end_book == book else 0
    end_chapter = end_parts[offset] if len(end_parts) > offset else None
    end_verse = end_parts[offset + 1] if len(end_parts) > offset + 1 else None
    return _format_range_end(end_book, end_chapter, end_verse)


@lru_cache(maxsize=256)
def expand_osis_reference(reference: str) -> frozenset[int]:
    """Return the set of verse identifiers covered by the supplied OSIS reference."""

    try:
        normalized = pb.get_references(_osis_to_readable(reference))
    except Exception:  # pragma: no cover - defensive parsing guard
        return frozenset()

    verse_ids: list[int] = []
    for entry in normalized:
        try:
            verse_ids.extend(pb.convert_reference_to_verse_ids(entry))
        except Exception:  # pragma: no cover - pythonbible safety net
            return frozenset()
    return frozenset(verse_ids)


def osis_intersects(a: str, b: str) -> bool:
    """Determine if two OSIS ranges intersect (basic overlap check)."""

    ids_a = expand_osis_reference(a)
    ids_b = expand_osis_reference(b)
    if not ids_a or not ids_b:
        return False
    return not ids_a.isdisjoint(ids_b)


def classify_osis_matches(
    detected: Sequence[str], hints: Sequence[str]
) -> tuple[list[str], list[str]]:
    """Separate hint references into those intersecting detected ranges and the rest."""

    detected_clean = [ref for ref in detected if ref]
    matched: list[str] = []
    unmatched: list[str] = []

    for hint in hints:
        if not hint:
            continue
        if not detected_clean:
            unmatched.append(hint)
            continue
        try:
            intersects = any(osis_intersects(candidate, hint) for candidate in detected_clean)
        except Exception:  # pragma: no cover - intersection should never fail but be safe
            intersects = False
        if intersects:
            if hint not in matched:
                matched.append(hint)
        elif hint not in unmatched:
            unmatched.append(hint)

    return matched, unmatched
