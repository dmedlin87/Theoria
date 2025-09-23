"""Utilities for turning parsed text into Theo Engine passages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


@dataclass
class Chunk:
    text: str
    start_char: int
    end_char: int
    page_no: int | None = None


def chunk_text(text: str, max_tokens: int = 900) -> List[Chunk]:
    """Chunk text by paragraphs while respecting an approximate token budget."""

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[Chunk] = []
    buffer: list[str] = []
    token_count = 0
    cursor = 0

    def flush() -> None:
        nonlocal buffer, token_count, cursor
        if not buffer:
            return
        chunk_text = "\n\n".join(buffer)
        start = cursor
        end = start + len(chunk_text)
        chunks.append(Chunk(text=chunk_text, start_char=start, end_char=end))
        cursor = end + 2  # account for paragraph break
        buffer = []
        token_count = 0

    for paragraph in paragraphs:
        para_tokens = len(paragraph.split())
        if token_count and token_count + para_tokens > max_tokens:
            flush()
        buffer.append(paragraph)
        token_count += para_tokens
    flush()

    if not chunks:
        chunks.append(Chunk(text=text.strip(), start_char=0, end_char=len(text.strip())))

    return chunks
