from __future__ import annotations

from typing import Sequence


class VerseChunk:
    osis: str
    text: str


def fetch_passage(osis: str, *, translation: str | None = ...) -> Sequence[VerseChunk]: ...


__all__ = ["VerseChunk", "fetch_passage"]
