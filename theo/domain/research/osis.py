"""OSIS scripture reference helpers shared across the domain."""
from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any, Iterable

try:  # pragma: no cover - optional dependency in lightweight tests
    import pythonbible as pb
except ModuleNotFoundError:  # pragma: no cover - stub out optional helpers
    pb = None  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover - typing aid only
    from pythonbible import Book, NormalizedReference
else:
    Book = Any  # type: ignore[assignment]
    NormalizedReference = Any  # type: ignore[assignment]

if pb is not None:  # pragma: no branch - guarded by import above
    Book = pb.Book  # type: ignore[assignment]
    NormalizedReference = pb.NormalizedReference  # type: ignore[assignment]

if pb is not None:
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
else:  # pragma: no cover - minimal fallback when dependency missing
    OSIS_BOOK_NAMES = {}
    KNOWN_BOOK_CODES = set()


def format_osis(reference: NormalizedReference) -> str:
    """Format a pythonbible NormalizedReference into OSIS notation."""

    if pb is None:
        raise RuntimeError("pythonbible is required to format OSIS references")

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


def _format_range_end(
    text_value: str,
    book: str,
    chapter: str | None,
    verse: str | None,
    end_book: str | None,
    end_chapter: str | None,
    end_verse: str | None,
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


def osis_to_readable(reference: str) -> str:
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

    end_parts = [part for part in rest[0].split(".") if part]
    if not end_parts:
        return text_value

    if verse is not None:
        if len(end_parts) == 1:
            return f"{text_value}-{end_parts[0]}"
        if len(end_parts) == 2:
            if end_parts[0] in KNOWN_BOOK_CODES:
                return _format_range_end(
                    text_value, book, chapter, verse, end_parts[0], end_parts[1], None
                )
            if chapter is not None and end_parts[0] == chapter:
                return f"{text_value}-{end_parts[1]}"
            return f"{text_value}-{end_parts[0]}:{end_parts[1]}"

        if end_parts and end_parts[0] in KNOWN_BOOK_CODES:
            end_book = end_parts[0]
            remaining = end_parts[1:]
        else:
            end_book = book
            remaining = end_parts

        end_chapter = remaining[0] if remaining else None
        end_verse = remaining[1] if len(remaining) > 1 else None
        return _format_range_end(
            text_value, book, chapter, verse, end_book, end_chapter, end_verse
        )

    if len(end_parts) == 1:
        return f"{text_value}-{end_parts[0]}"
    if len(end_parts) == 2:
        if end_parts[0] in KNOWN_BOOK_CODES:
            return _format_range_end(
                text_value, book, chapter, verse, end_parts[0], end_parts[1], None
            )
        return _format_range_end(
            text_value, book, chapter, verse, None, end_parts[0], end_parts[1]
        )

    if end_parts and end_parts[0] in KNOWN_BOOK_CODES:
        end_book = end_parts[0]
        remaining = end_parts[1:]
    else:
        end_book = book
        remaining = end_parts

    end_chapter = remaining[0] if remaining else None
    end_verse = remaining[1] if len(remaining) > 1 else None
    return _format_range_end(
        text_value, book, chapter, verse, end_book, end_chapter, end_verse
    )


@lru_cache(maxsize=256)
def expand_osis_reference(reference: str) -> frozenset[int]:
    """Return the set of verse identifiers covered by the supplied OSIS reference."""

    if pb is None:
        return frozenset()

    try:
        normalized = pb.get_references(osis_to_readable(reference))
    except Exception:
        return frozenset()

    verse_ids: list[int] = []
    for entry in normalized:
        try:
            verse_ids.extend(pb.convert_reference_to_verse_ids(entry))
        except Exception:
            return frozenset()
    return frozenset(verse_ids)


def verse_ids_to_osis(verse_ids: Iterable[int]) -> Iterable[str]:
    """Yield OSIS strings for each verse identifier in *verse_ids*."""

    if pb is None:
        return ()

    for verse_id in verse_ids:
        references = pb.convert_verse_ids_to_references([verse_id])
        if not references:
            continue
        yield format_osis(references[0])


__all__ = [
    "OSIS_BOOK_NAMES",
    "KNOWN_BOOK_CODES",
    "expand_osis_reference",
    "format_osis",
    "osis_to_readable",
    "verse_ids_to_osis",
]
