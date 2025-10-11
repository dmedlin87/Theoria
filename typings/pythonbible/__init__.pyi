from __future__ import annotations

from enum import Enum
from typing import Iterable, Sequence


class Book(Enum):
    GENESIS: Book
    EXODUS: Book
    LEVITICUS: Book
    NUMBERS: Book
    DEUTERONOMY: Book
    JOSHUA: Book
    JUDGES: Book
    RUTH: Book
    SAMUEL_1: Book
    SAMUEL_2: Book
    KINGS_1: Book
    KINGS_2: Book
    CHRONICLES_1: Book
    CHRONICLES_2: Book
    EZRA: Book
    NEHEMIAH: Book
    ESTHER: Book
    JOB: Book
    PSALMS: Book
    PROVERBS: Book
    ECCLESIASTES: Book
    SONG_OF_SONGS: Book
    ISAIAH: Book
    JEREMIAH: Book
    LAMENTATIONS: Book
    EZEKIEL: Book
    DANIEL: Book
    HOSEA: Book
    JOEL: Book
    AMOS: Book
    OBADIAH: Book
    JONAH: Book
    MICAH: Book
    NAHUM: Book
    HABAKKUK: Book
    ZEPHANIAH: Book
    HAGGAI: Book
    ZECHARIAH: Book
    MALACHI: Book
    MATTHEW: Book
    MARK: Book
    LUKE: Book
    JOHN: Book
    ACTS: Book
    ROMANS: Book
    CORINTHIANS_1: Book
    CORINTHIANS_2: Book
    GALATIANS: Book
    EPHESIANS: Book
    PHILIPPIANS: Book
    COLOSSIANS: Book
    THESSALONIANS_1: Book
    THESSALONIANS_2: Book
    TIMOTHY_1: Book
    TIMOTHY_2: Book
    TITUS: Book
    PHILEMON: Book
    HEBREWS: Book
    JAMES: Book
    PETER_1: Book
    PETER_2: Book
    JOHN_1: Book
    JOHN_2: Book
    JOHN_3: Book
    JUDE: Book
    REVELATION: Book
    TOBIT: Book
    WISDOM_OF_SOLOMON: Book
    ECCLESIASTICUS: Book
    ESDRAS_1: Book
    MACCABEES_1: Book
    MACCABEES_2: Book


class NormalizedReference:
    book: Book
    start_chapter: int
    start_verse: int
    end_chapter: int
    end_verse: int
    end_book: Book | None

    def __init__(self, *args: object, **kwargs: object) -> None: ...


def convert_reference_to_verse_ids(reference: NormalizedReference | str) -> list[int]: ...

def convert_verse_ids_to_references(verse_ids: Sequence[int]) -> list[NormalizedReference]: ...

def get_references(text: str) -> list[NormalizedReference]: ...

def get_matching_verse_ids(reference: str) -> list[int]: ...

def get_books() -> Iterable[Book]: ...

__all__ = [
    "Book",
    "NormalizedReference",
    "convert_reference_to_verse_ids",
    "convert_verse_ids_to_references",
    "get_references",
    "get_matching_verse_ids",
    "get_books",
]
