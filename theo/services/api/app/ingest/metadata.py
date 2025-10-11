"""Metadata helpers for the ingestion pipeline."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from collections.abc import Mapping
from typing import Protocol, TypeAlias

import yaml

from .exceptions import UnsupportedSourceError
from .osis import DetectedOsis, classify_osis_matches
from .parsers import (
    PDF_EXTRACTION_UNSUPPORTED,
    ParserResult,
    TranscriptSegment as ParsedTranscriptSegment,
    load_transcript,
    parse_audio_document,
    parse_docx_document,
    parse_html_document,
    parse_pdf_document,
    read_text_file,
)
from .chunking import Chunk, chunk_text, chunk_transcript
from .sanitizer import sanitize_passage_text


JSONPrimitive: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONPrimitive | list["JSONValue"] | dict[str, "JSONValue"]
Frontmatter: TypeAlias = dict[str, object]
FrontmatterMapping: TypeAlias = Mapping[str, object]


class _TopicsProvider(Protocol):
    topics: object


class _ChunkSettings(Protocol):
    max_chunk_tokens: int


class _PdfChunkSettings(_ChunkSettings, Protocol):
    doc_max_pages: int


def parse_frontmatter_from_markdown(text: str) -> tuple[Frontmatter, str]:
    """Split a markdown document into frontmatter and body."""

    if not text.startswith("---"):
        return {}, text

    lines = text.splitlines()
    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break

    if end_index is None:
        return {}, text

    frontmatter_text = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :])
    loaded = yaml.safe_load(frontmatter_text) or {}
    data: Frontmatter
    if isinstance(loaded, dict):
        data = {str(key): value for key, value in loaded.items()}
    else:
        data = {}
    return data, body


def parse_text_file(path: Path) -> tuple[str, Frontmatter]:
    """Read a text file, extracting markdown frontmatter when present."""

    try:
        content = read_text_file(path)
    except (UnicodeDecodeError, OSError) as exc:
        raise UnsupportedSourceError(
            f"Unable to decode text file '{path.name}'"
        ) from exc
    if path.suffix.lower() in {".md", ".markdown"}:
        frontmatter, body = parse_frontmatter_from_markdown(content)
        return body, frontmatter
    return content, {}


def load_frontmatter(frontmatter: Frontmatter | None) -> Frontmatter:
    """Normalise a frontmatter mapping for downstream processing."""

    if not frontmatter:
        return {}
    return dict(frontmatter)


def detect_source_type(path: Path, frontmatter: FrontmatterMapping) -> str:
    if frontmatter.get("source_type"):
        return str(frontmatter["source_type"])
    ext = path.suffix.lower()
    if ext in {".md", ".markdown"}:
        return "markdown"
    if ext == ".txt":
        return "txt"
    if ext == ".pdf":
        return "pdf"
    if ext in {".html", ".htm", ".xhtml"}:
        return "html"
    if ext in {".vtt", ".webvtt", ".srt", ".json"}:
        return "transcript"
    if ext == ".docx":
        return "docx"
    if ext in {".mp3", ".wav", ".m4a"}:
        return "audio"
    return "file"


def merge_metadata(base: FrontmatterMapping, overrides: FrontmatterMapping) -> Frontmatter:
    """Merge metadata dictionaries preferring override values when present."""

    combined: Frontmatter = dict(base)
    for key, override_value in overrides.items():
        if override_value is None:
            continue
        base_value = combined.get(key)
        if isinstance(base_value, Mapping) and isinstance(override_value, Mapping):
            combined[key] = merge_metadata(dict(base_value), dict(override_value))
        else:
            combined[key] = override_value
    return combined


def serialise_frontmatter(frontmatter: FrontmatterMapping) -> str:
    """Render a frontmatter dictionary to JSON, normalising complex types."""

    def _normalise(value: object) -> JSONValue:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, Mapping):
            return {str(k): _normalise(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_normalise(item) for item in value]
        return str(value)

    normalised: dict[str, JSONValue] = {
        key: _normalise(val) for key, val in frontmatter.items()
    }
    return json.dumps(normalised, indent=2, ensure_ascii=False)


def ensure_list(value: object) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _normalise_guardrail_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalise_guardrail_collection(value: object) -> list[str] | None:
    if value is None:
        return None
    items: list[str] = []
    if isinstance(value, (list, tuple, set)):
        for item in value:
            text = _normalise_guardrail_value(item)
            if text:
                items.append(text)
    else:
        for part in re.split(r"[,;]", str(value)):
            text = _normalise_guardrail_value(part)
            if text:
                items.append(text)
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique or None


def extract_guardrail_profile(
    frontmatter: FrontmatterMapping,
) -> tuple[str | None, list[str] | None]:
    tradition = _normalise_guardrail_value(frontmatter.get("theological_tradition"))
    topic_domains = _normalise_guardrail_collection(
        frontmatter.get("topic_domains") or frontmatter.get("topic_domain")
    )

    tag_sources: list[str] = []
    for key in ("admin_tags", "tags"):
        entries = ensure_list(frontmatter.get(key)) or []
        tag_sources.extend(entries)

    for raw_tag in tag_sources:
        tag = str(raw_tag)
        if ":" not in tag:
            continue
        prefix, value = tag.split(":", 1)
        prefix_key = prefix.strip().lower()
        value_text = _normalise_guardrail_value(value)
        if not value_text:
            continue
        if prefix_key in {"tradition", "confession"} and not tradition:
            tradition = value_text
        if prefix_key in {"domain", "topic_domain"}:
            topic_domains = topic_domains or []
            if value_text not in topic_domains:
                topic_domains.append(value_text)

    return tradition, topic_domains or None


def coerce_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed.date()
    except ValueError:
        return None


def coerce_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def coerce_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float, str)):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def derive_duration_from_chunks(chunks: list[Chunk]) -> int | None:
    for chunk in reversed(chunks):
        if chunk.t_end is not None:
            return coerce_int(chunk.t_end)
    return None


def normalise_passage_meta(
    detected: DetectedOsis,
    hints: list[str] | None,
    *,
    parser: str,
    parser_version: str,
    chunker_version: str,
    chunk_index: int,
    speakers: list[str] | None = None,
) -> dict[str, object]:
    hint_list = [hint for hint in hints or [] if hint]
    detected_refs = [ref for ref in detected.all if ref]
    matched_hints, unmatched_hints = classify_osis_matches(
        ([detected.primary] if detected.primary else []) + detected_refs,
        hint_list,
    )

    combined_refs = sorted({*detected_refs, *matched_hints, *unmatched_hints})

    meta: dict[str, object] = {
        "parser": parser,
        "parser_version": parser_version,
        "chunker_version": chunker_version,
        "chunk_index": chunk_index,
    }
    if combined_refs:
        meta["osis_refs_all"] = combined_refs
    if detected_refs:
        meta["osis_refs_detected"] = sorted(detected_refs)
    if matched_hints:
        meta["osis_refs_hints"] = matched_hints
    if unmatched_hints:
        meta["osis_refs_unmatched"] = unmatched_hints
    if detected.primary:
        meta["primary_osis"] = detected.primary
    if speakers:
        meta["speakers"] = speakers
    return meta


class HTMLMetadataParser(HTMLParser):
    """Parse minimal metadata from an HTML page."""

    def __init__(self) -> None:
        super().__init__()
        self.title: str | None = None
        self.canonical_url: str | None = None
        self._capture_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if name == "title":
            self._capture_title = True
            return

        attr_map = {key.lower(): (value or "") for key, value in attrs}
        if name == "link":
            rel = attr_map.get("rel", "")
            rel_values = {item.strip().lower() for item in rel.split() if item}
            if "canonical" in rel_values and not self.canonical_url:
                href = attr_map.get("href")
                if href:
                    self.canonical_url = href.strip()
        elif name == "meta":
            prop = attr_map.get("property") or attr_map.get("name") or ""
            prop_lower = prop.lower()
            content = attr_map.get("content")
            if content:
                content = content.strip()
            if not content:
                return
            if prop_lower == "og:title" and not self.title:
                self.title = content
            if prop_lower in {"og:url", "twitter:url"} and not self.canonical_url:
                self.canonical_url = content

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._capture_title = False

    def handle_data(self, data: str) -> None:
        if not self._capture_title:
            return
        text = data.strip()
        if text and not self.title:
            self.title = text


class HTMLTextExtractor(HTMLParser):
    """Convert HTML into a normalized text representation."""

    _BLOCK_TAGS = {
        "article",
        "aside",
        "blockquote",
        "br",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "p",
        "section",
    }

    _SKIP_TAGS = {
        "script",
        "style",
        "noscript",
        "template",
    }

    def __init__(self) -> None:
        super().__init__()
        self._buffer: list[str] = []
        self._skip_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if name in self._SKIP_TAGS:
            self._skip_stack.append(name)
            return
        if name in self._BLOCK_TAGS:
            self._buffer.append("\n")

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if name in self._SKIP_TAGS:
            if self._skip_stack and self._skip_stack[-1] == name:
                self._skip_stack.pop()
            return
        if name in self._BLOCK_TAGS:
            self._buffer.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_stack:
            return
        text = unescape(data)
        if text.strip():
            self._buffer.append(text)

    def get_text(self) -> str:
        combined = "".join(self._buffer)
        lines = [line.strip() for line in combined.splitlines()]
        normalized = "\n".join(line for line in lines if line)
        return normalized.strip()


def parse_html_metadata(html: str) -> dict[str, str | None]:
    parser = HTMLMetadataParser()
    parser.feed(html)
    parser.close()
    return {
        "title": parser.title,
        "canonical_url": parser.canonical_url,
    }


def html_to_text(html: str) -> str:
    extractor = HTMLTextExtractor()
    extractor.feed(html)
    extractor.close()
    return extractor.get_text()


def normalise_source_url(value: str | None) -> str | None:
    from urllib.parse import urlparse, urlunparse

    _SAFE_SOURCE_URL_SCHEMES = {"http", "https"}

    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None

    if candidate.startswith("/"):
        return "/" + candidate.lstrip("/")

    parsed = urlparse(candidate)

    if parsed.scheme:
        scheme = parsed.scheme.lower()
        if scheme in _SAFE_SOURCE_URL_SCHEMES:
            normalised = parsed._replace(scheme=scheme)
            return urlunparse(normalised)
        return None

    if parsed.netloc:
        normalised = parsed._replace(scheme="https")
        return urlunparse(normalised)

    if parsed.path:
        return "/" + parsed.path.lstrip("/")

    return None


def collect_topics(
    document: _TopicsProvider,
    frontmatter: FrontmatterMapping,
) -> list[str]:
    topics: list[str] = []
    doc_topics = document.topics
    if isinstance(doc_topics, dict):
        topics.extend(doc_topics.get("all") or [])
    elif isinstance(doc_topics, list):
        topics.extend(str(item) for item in doc_topics if item)
    additional = ensure_list(frontmatter.get("topics")) or []
    for item in additional:
        if item not in topics:
            topics.append(item)
    return [topic for topic in (topic.strip() for topic in topics) if topic]


def normalise_topics_field(
    *candidates: object,
) -> dict[str, str | list[str]] | None:
    values: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        items = ensure_list(candidate) or []
        for item in items:
            cleaned = item.strip()
            if not cleaned:
                continue
            if cleaned not in seen:
                seen.add(cleaned)
                values.append(cleaned)
    if not values:
        return None
    return {"primary": values[0], "all": values}


def build_source_ref(
    video_identifier: str | None, source_url: str | None, t_start: float | None
) -> str | None:
    if video_identifier is None or t_start is None:
        return None
    prefix = "video"
    if source_url:
        lowered = source_url.lower()
        if "youtube" in lowered or "youtu.be" in lowered:
            prefix = "youtube"
        elif "vimeo" in lowered:
            prefix = "vimeo"
    seconds = max(0, int(t_start))
    minutes, remaining = divmod(seconds, 60)
    return f"{prefix}:{video_identifier}#t={minutes:02d}:{remaining:02d}"


def truncate(text: str, limit: int = 280) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def prepare_text_chunks(text: str, *, settings: _ChunkSettings) -> ParserResult:
    chunks = chunk_text(text, max_tokens=settings.max_chunk_tokens)
    return ParserResult(
        text=text, chunks=chunks, parser="plain_text", parser_version="0.1.0"
    )


def prepare_pdf_chunks(path: Path, *, settings: _PdfChunkSettings) -> ParserResult:
    result = parse_pdf_document(
        path,
        max_pages=settings.doc_max_pages,
        max_tokens=settings.max_chunk_tokens,
    )
    if result is PDF_EXTRACTION_UNSUPPORTED:
        raise UnsupportedSourceError(
            "Unable to extract text from PDF; the file may be password protected or corrupted."
        )
    if not isinstance(result, ParserResult):
        raise UnsupportedSourceError("PDF contained no extractable text")
    if not result.chunks:
        raise UnsupportedSourceError("PDF contained no extractable text")
    return result


def prepare_transcript_chunks(
    segments: list[ParsedTranscriptSegment],
    *,
    settings: _ChunkSettings,
) -> ParserResult:
    if not segments:
        raise UnsupportedSourceError("Transcript file contained no segments")
    chunks = chunk_transcript(
        segments,
        max_tokens=settings.max_chunk_tokens,
        max_window_seconds=getattr(settings, "transcript_max_window", 40.0),
    )
    text = " ".join(segment.text for segment in segments)
    return ParserResult(
        text=text, chunks=chunks, parser="transcript", parser_version="0.3.0"
    )


def sanitise_chunks(chunks: list[Chunk]) -> tuple[list[str], list[str]]:
    raw_texts: list[str] = []
    sanitized_texts: list[str] = []
    for chunk in chunks:
        raw_value = chunk.text
        sanitized_value = sanitize_passage_text(raw_value)
        raw_texts.append(raw_value)
        sanitized_texts.append(sanitized_value)
    return raw_texts, sanitized_texts

