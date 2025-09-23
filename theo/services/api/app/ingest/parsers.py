"""Lightweight content parsers for ingestion pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


from pdfminer.high_level import extract_text
import webvtt


@dataclass(slots=True)
class ParsedPage:
    text: str
    page_no: int | None = None


@dataclass(slots=True)
class TranscriptSegment:
    text: str
    start: float
    end: float
    speaker: str | None = None


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_pdf(path: Path, *, max_pages: int | None = None) -> list[ParsedPage]:
    """Extract text from a PDF file page-by-page using pdfminer."""

    pages: list[ParsedPage] = []
    page_index = 0
    while True:
        if max_pages is not None and page_index >= max_pages:
            break
        text = extract_text(str(path), page_numbers=[page_index])
        if not text:
            break
        cleaned = "\n".join(line.rstrip() for line in text.splitlines()).strip()
        pages.append(ParsedPage(text=cleaned, page_no=page_index + 1))
        page_index += 1
    return pages


def parse_transcript_vtt(path: Path) -> list[TranscriptSegment]:
    """Parse a WebVTT transcript file into structured segments."""

    segments: list[TranscriptSegment] = []
    for entry in webvtt.read(path):
        text = " ".join(entry.text.split())
        if not text:
            continue

        speaker: str | None = None
        if ":" in text:
            potential, remainder = text.split(":", 1)
            if potential.strip().istitle() or potential.strip().startswith("Speaker") or potential.strip().endswith("Narrator"):
                speaker = potential.strip()
                text = remainder.strip()

        segments.append(
            TranscriptSegment(
                text=text,
                start=float(entry.start_in_seconds),
                end=float(entry.end_in_seconds),
                speaker=speaker,
            )
        )
    return segments


def parse_transcript_json(path: Path) -> list[TranscriptSegment]:
    """Parse a JSON transcript array."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    segments: list[TranscriptSegment] = []
    if isinstance(payload, dict) and "events" in payload:
        payload = payload["events"]
    if not isinstance(payload, list):
        return segments
    for item in payload:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        start = float(item.get("start", 0.0))
        duration = item.get("duration")
        if duration is not None:
            end = start + float(duration)
        else:
            end = float(item.get("end", start))
        segments.append(
            TranscriptSegment(
                text=text,
                start=start,
                end=end,
                speaker=item.get("speaker"),
            )
        )
    return segments


def load_transcript(path: Path) -> list[TranscriptSegment]:
    suffix = path.suffix.lower()
    if suffix in {".vtt", ".webvtt"}:
        return parse_transcript_vtt(path)
    if suffix == ".srt":
        vtt = webvtt.from_srt(path)
        segments: list[TranscriptSegment] = []
        for entry in vtt:
            text = " ".join(entry.text.split())
            if not text:
                continue
            segments.append(
                TranscriptSegment(
                    text=text,
                    start=float(entry.start_in_seconds),
                    end=float(entry.end_in_seconds),
                )
            )
        return segments
    if suffix == ".json":
        return parse_transcript_json(path)
    raise ValueError(f"Unsupported transcript format: {suffix}")
