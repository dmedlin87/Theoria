"""Utilities for turning parsed text into Theo Engine passages."""

from __future__ import annotations

from dataclasses import dataclass

from typing import Iterable

from .parsers import TranscriptSegment



@dataclass(slots=True)
class Chunk:
    """Normalized chunk emitted from the chunker."""

    text: str
    start_char: int
    end_char: int
    page_no: int | None = None
    index: int | None = None
    t_start: float | None = None
    t_end: float | None = None
    speakers: list[str] | None = None



@dataclass(slots=True)
class _Paragraph:
    text: str
    start: int
    end: int

    @property
    def tokens(self) -> int:
        return len(_tokenise(self.text))


def _tokenise(text: str) -> list[str]:
    return [token for token in text.split() if token]


def _split_long_paragraph(paragraph: _Paragraph, hard_cap: int) -> Iterable[_Paragraph]:
    """Split a paragraph into pseudo-sentences when it breaches the hard cap."""

    tokens = _tokenise(paragraph.text)
    if len(tokens) <= hard_cap:
        yield paragraph
        return

    # Fallback heuristic: split on sentence-ish boundaries while preserving offsets.
    text = paragraph.text
    cursor = paragraph.start
    sentence_start = 0
    for idx, char in enumerate(text):
        if char not in {".", "?", "!"}:
            continue
        next_idx = idx + 1
        if next_idx < len(text) and text[next_idx].isalnum():
            continue
        segment = text[sentence_start : next_idx + 1].strip()
        if not segment:
            continue
        offset = text.find(segment, sentence_start)
        start = cursor + offset
        end = start + len(segment)
        yield _Paragraph(text=segment, start=start, end=end)
        sentence_start = next_idx + 1

    tail = text[sentence_start:].strip()
    if tail:
        offset = text.find(tail, sentence_start)
        start = cursor + offset
        end = start + len(tail)
        yield _Paragraph(text=tail, start=start, end=end)


def _iter_paragraphs(text: str) -> Iterable[_Paragraph]:
    cursor = 0
    for raw in text.split("\n\n"):
        if not raw.strip():
            cursor += len(raw) + 2
            continue
        stripped = raw.strip()
        start = text.find(stripped, cursor)
        if start == -1:
            start = cursor
        end = start + len(stripped)
        cursor = end
        yield _Paragraph(text=stripped, start=start, end=end)


def chunk_text(
    text: str,
    *,
    max_tokens: int = 900,
    min_tokens: int = 500,
    hard_cap: int = 1200,
) -> list[Chunk]:
    """Chunk text by paragraphs while respecting token budgets."""

    if not text.strip():
        return [Chunk(text="", start_char=0, end_char=0, index=0)]

    paragraphs: list[_Paragraph] = []
    for paragraph in _iter_paragraphs(text):
        paragraphs.extend(list(_split_long_paragraph(paragraph, hard_cap)))

    chunks: list[Chunk] = []
    buffer: list[_Paragraph] = []
    token_count = 0

    def flush() -> None:
        nonlocal buffer, token_count
        if not buffer:
            return
        chunk_text_value = "\n\n".join(part.text for part in buffer)
        start = buffer[0].start
        end = buffer[-1].end
        chunks.append(
            Chunk(
                text=chunk_text_value,
                start_char=start,
                end_char=end,
                page_no=None,
                index=len(chunks),
            )
        )
        buffer = []
        token_count = 0

    for paragraph in paragraphs:
        para_tokens = paragraph.tokens
        if buffer and token_count + para_tokens > max_tokens and token_count >= min_tokens:
            flush()

        if token_count and token_count + para_tokens > hard_cap:
            flush()

        buffer.append(paragraph)
        token_count += para_tokens

        if token_count >= hard_cap:
            flush()

    flush()

    if not chunks:
        stripped = text.strip()
        chunks.append(
            Chunk(text=stripped, start_char=0, end_char=len(stripped), page_no=None, index=0)
        )

    return chunks


def chunk_transcript(
    segments: Iterable[TranscriptSegment],
    *,
    max_tokens: int = 900,
    hard_cap: int = 1200,
    max_window_seconds: float = 40.0,
) -> list[Chunk]:
    """Chunk transcript segments while preserving temporal anchors."""

    chunks: list[Chunk] = []
    buffer: list[TranscriptSegment] = []
    token_count = 0
    char_cursor = 0

    def flush() -> None:
        nonlocal buffer, token_count, char_cursor
        if not buffer:
            return
        text = " ".join(seg.text for seg in buffer)
        start_time = buffer[0].start
        end_time = buffer[-1].end
        speakers = sorted({seg.speaker for seg in buffer if seg.speaker}) or None
        chunk = Chunk(
            text=text,
            start_char=char_cursor,
            end_char=char_cursor + len(text),
            index=len(chunks),
            t_start=start_time,
            t_end=end_time,
            speakers=speakers,
        )
        chunks.append(chunk)
        char_cursor += len(text) + 1
        buffer = []
        token_count = 0

    for segment in segments:
        tokens = len(_tokenise(segment.text))
        if buffer:
            window = segment.end - buffer[0].start
            if token_count >= max_tokens or window > max_window_seconds:
                flush()
        if token_count and token_count + tokens > hard_cap:
            flush()

        buffer.append(segment)
        token_count += tokens

        if token_count >= hard_cap:
            flush()

    flush()
    return chunks

