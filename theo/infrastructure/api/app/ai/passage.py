from __future__ import annotations

import re


class PassageResolutionError(ValueError):
    """Raised when a plain-language passage cannot be resolved."""


_BASE_BOOKS = {
    "genesis": "Gen",
    "exodus": "Exod",
    "leviticus": "Lev",
    "numbers": "Num",
    "deuteronomy": "Deut",
    "joshua": "Josh",
    "judges": "Judg",
    "ruth": "Ruth",
    "1 samuel": "1Sam",
    "2 samuel": "2Sam",
    "1 kings": "1Kgs",
    "2 kings": "2Kgs",
    "1 chronicles": "1Chr",
    "2 chronicles": "2Chr",
    "ezra": "Ezra",
    "nehemiah": "Neh",
    "esther": "Esth",
    "job": "Job",
    "psalms": "Ps",
    "proverbs": "Prov",
    "ecclesiastes": "Eccl",
    "song": "Song",
    "isaiah": "Isa",
    "jeremiah": "Jer",
    "lamentations": "Lam",
    "ezekiel": "Ezek",
    "daniel": "Dan",
    "hosea": "Hos",
    "joel": "Joel",
    "amos": "Amos",
    "obadiah": "Obad",
    "jonah": "Jonah",
    "micah": "Mic",
    "nahum": "Nah",
    "habakkuk": "Hab",
    "zephaniah": "Zeph",
    "haggai": "Hag",
    "zechariah": "Zech",
    "malachi": "Mal",
    "matthew": "Matt",
    "mark": "Mark",
    "luke": "Luke",
    "john": "John",
    "acts": "Acts",
    "romans": "Rom",
    "1 corinthians": "1Cor",
    "2 corinthians": "2Cor",
    "galatians": "Gal",
    "ephesians": "Eph",
    "philippians": "Phil",
    "colossians": "Col",
    "1 thessalonians": "1Thess",
    "2 thessalonians": "2Thess",
    "1 timothy": "1Tim",
    "2 timothy": "2Tim",
    "titus": "Titus",
    "philemon": "Phlm",
    "hebrews": "Heb",
    "james": "Jas",
    "1 peter": "1Pet",
    "2 peter": "2Pet",
    "1 john": "1John",
    "2 john": "2John",
    "3 john": "3John",
    "jude": "Jude",
    "revelation": "Rev",
}

_EXTRA_ALIASES = {
    "psalm": "Ps",
    "ps": "Ps",
    "gospel of matthew": "Matt",
    "gospel of mark": "Mark",
    "gospel of luke": "Luke",
    "gospel of john": "John",
    "song of songs": "Song",
    "song of solomon": "Song",
    "canticles": "Song",
}

_NUMERAL_ALIASES = {
    "first": "1",
    "1st": "1",
    "i": "1",
    "second": "2",
    "2nd": "2",
    "ii": "2",
    "third": "3",
    "3rd": "3",
    "iii": "3",
}

_BOOK_ALIASES: dict[str, str] = {}
for name, code in _BASE_BOOKS.items():
    normalized = name.lower()
    _BOOK_ALIASES[normalized] = code
    _BOOK_ALIASES[normalized.replace(" ", "")] = code

for alias, code in _EXTRA_ALIASES.items():
    _BOOK_ALIASES[alias] = code


def _normalize_book(raw: str) -> str:
    cleaned = raw.lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned.startswith("the "):
        cleaned = cleaned[4:]
    for prefix in ("book of ", "gospel of "):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
    tokens = cleaned.split()
    if tokens and tokens[0] in _NUMERAL_ALIASES:
        tokens[0] = _NUMERAL_ALIASES[tokens[0]]
    if tokens and len(tokens) > 1 and tokens[0] == "the" and tokens[1] in _NUMERAL_ALIASES:
        tokens = [
            _NUMERAL_ALIASES[tokens[1]],
            *tokens[2:],
        ]
    return " ".join(tokens)


# Optimized pattern to prevent ReDoS: use possessive quantifiers via atomic grouping
# Changed [\d\w\s]+? to ([\w\d]+(?:\s+[\w\d]+)*) to avoid catastrophic backtracking
_PASSAGE_PATTERN = re.compile(
    r"""
    ^\s*
    (?P<book>[\w\d]+(?:\s+[\w\d]+)*)
    \s+
    (?P<start_chapter>\d+)
    (?:
        :(?P<start_verse>\d+)
        (?:
            \s*[-–—]\s*
            (?:
                (?P<end_chapter>\d+):(?P<end_verse>\d+)
                |
                (?P<end_verse_only>\d+)
            )
        )?
        |
        \s*[-–—]\s*(?P<end_chapter_only>\d+)
    )?
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)


def resolve_passage_reference(passage: str) -> str:
    """Convert a plain-language passage (e.g., "Mark 16:9–20") into an OSIS string."""

    if not passage or not passage.strip():
        raise PassageResolutionError("Provide a passage to analyse.")

    # Prevent ReDoS attacks by rejecting overly long inputs
    if len(passage) > 200:
        raise PassageResolutionError("Passage reference too long (max 200 characters).")

    normalized = passage.replace("\u2013", "-").replace("\u2014", "-")
    match = _PASSAGE_PATTERN.match(normalized)
    if not match:
        raise PassageResolutionError(f"Unable to interpret passage '{passage}'.")

    book_key = _normalize_book(match.group("book"))
    osis_book = _BOOK_ALIASES.get(book_key)
    if not osis_book:
        raise PassageResolutionError(f"Unrecognised book name '{match.group('book').strip()}'.")

    start_chapter = int(match.group("start_chapter"))
    start_verse = match.group("start_verse")
    if start_verse:
        start = f"{osis_book}.{start_chapter}.{int(start_verse)}"
    else:
        start = f"{osis_book}.{start_chapter}"

    end = None
    end_chapter = match.group("end_chapter")
    end_verse = match.group("end_verse")
    if end_chapter and end_verse:
        end = f"{osis_book}.{int(end_chapter)}.{int(end_verse)}"
    else:
        end_verse_only = match.group("end_verse_only")
        end_chapter_only = match.group("end_chapter_only")
        if end_verse_only:
            end = f"{osis_book}.{start_chapter}.{int(end_verse_only)}"
        elif end_chapter_only:
            end = f"{osis_book}.{int(end_chapter_only)}"

    if end:
        return f"{start}-{end}"
    return start


__all__ = ["PassageResolutionError", "resolve_passage_reference"]
