"""Metadata helpers for the ingestion pipeline."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ..parsers import read_text_file


def parse_frontmatter_from_markdown(text: str) -> tuple[dict[str, Any], str]:
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
    data = yaml.safe_load(frontmatter_text) or {}
    if not isinstance(data, dict):
        data = {}
    return data, body


def parse_text_file(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        content = read_text_file(path)
    except (UnicodeDecodeError, OSError) as exc:
        from .exceptions import UnsupportedSourceError

        raise UnsupportedSourceError(
            f"Unable to decode text file '{path.name}'"
        ) from exc
    if path.suffix.lower() in {".md", ".markdown"}:
        frontmatter, body = parse_frontmatter_from_markdown(content)
        return body, frontmatter
    return content, {}


def load_frontmatter(frontmatter: dict[str, Any] | None) -> dict[str, Any]:
    if not frontmatter:
        return {}
    return dict(frontmatter)


def detect_source_type(path: Path, frontmatter: dict[str, Any]) -> str:
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
    if ext in {".vtt", ".webvtt", ".srt"}:
        return "transcript"
    if ext == ".json":
        return "transcript"
    if ext == ".docx":
        return "docx"
    if ext in {".mp3", ".wav", ".m4a"}:
        return "audio"

    return "file"


def merge_metadata(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    combined = {**base}
    combined.update({k: v for k, v in overrides.items() if v is not None})
    return combined


def serialise_frontmatter(frontmatter: dict[str, Any]) -> str:
    """Render a frontmatter dictionary to JSON, normalising complex types."""

    def _normalise(value: Any):
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {k: _normalise(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_normalise(item) for item in value]
        return str(value)

    normalised = {key: _normalise(val) for key, val in frontmatter.items()}
    return json.dumps(normalised, indent=2, ensure_ascii=False)


def normalise_passage_meta(
    detected,
    hints: list[str] | None,
    *,
    parser: str,
    parser_version: str,
    chunker_version: str,
    chunk_index: int,
    speakers: list[str] | None = None,
) -> dict[str, Any]:
    from ..osis import classify_osis_matches

    hint_list = [hint for hint in hints or [] if hint]
    detected_refs = [ref for ref in detected.all if ref]
    matched_hints, unmatched_hints = classify_osis_matches(
        ([detected.primary] if detected.primary else []) + detected_refs,
        hint_list,
    )

    combined_refs = sorted({*detected_refs, *matched_hints, *unmatched_hints})

    meta: dict[str, Any] = {
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


def coerce_date(value: Any) -> date | None:
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


def coerce_datetime(value: Any) -> datetime | None:
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


def ensure_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def normalise_guardrail_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalise_guardrail_collection(value: Any) -> list[str] | None:
    if value is None:
        return None
    items: list[str] = []
    if isinstance(value, (list, tuple, set)):
        for item in value:
            text = normalise_guardrail_value(item)
            if text:
                items.append(text)
    else:
        for part in re.split(r"[,;]", str(value)):
            text = normalise_guardrail_value(part)
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
    frontmatter: dict[str, Any]
) -> tuple[str | None, list[str] | None]:
    tradition = normalise_guardrail_value(frontmatter.get("theological_tradition"))
    topic_domains = normalise_guardrail_collection(
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
        value_text = normalise_guardrail_value(value)
        if not value_text:
            continue
        if prefix_key in {"tradition", "confession"} and not tradition:
            tradition = value_text
        if prefix_key in {"domain", "topic_domain"}:
            topic_domains = topic_domains or []
            if value_text not in topic_domains:
                topic_domains.append(value_text)

    return tradition, topic_domains or None


def collect_topics(document, frontmatter: dict[str, Any]) -> list[str]:
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


def normalise_topics_field(*candidates: Any) -> dict | None:
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


def coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def derive_duration_from_chunks(chunks) -> int | None:
    for chunk in reversed(chunks):
        if chunk.t_end is not None:
            return coerce_int(chunk.t_end)
    return None


__all__ = [
    "collect_topics",
    "coerce_date",
    "coerce_datetime",
    "coerce_int",
    "derive_duration_from_chunks",
    "detect_source_type",
    "ensure_list",
    "extract_guardrail_profile",
    "load_frontmatter",
    "merge_metadata",
    "normalise_guardrail_collection",
    "normalise_guardrail_value",
    "normalise_passage_meta",
    "normalise_source_url",
    "normalise_topics_field",
    "parse_frontmatter_from_markdown",
    "parse_text_file",
    "serialise_frontmatter",
]
