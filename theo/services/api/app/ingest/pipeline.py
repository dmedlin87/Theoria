"""Ingestion pipeline orchestration."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from sqlalchemy.orm import Session

from ..core.settings import get_settings
from ..db.models import Document, Passage
from .chunking import chunk_text
from .osis import DetectedOsis, detect_osis_references

class UnsupportedSourceError(ValueError):
    """Raised when the pipeline cannot parse an input file."""


def _parse_frontmatter_from_markdown(text: str) -> tuple[dict[str, Any], str]:
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


def _parse_text_file(path: Path) -> tuple[str, dict[str, Any]]:
    content = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".md", ".markdown"}:
        fm, body = _parse_frontmatter_from_markdown(content)
        return body, fm
    return content, {}


def _load_frontmatter(frontmatter: dict[str, Any] | None) -> dict[str, Any]:
    if not frontmatter:
        return {}
    return dict(frontmatter)


def _detect_source_type(path: Path, frontmatter: dict[str, Any]) -> str:
    if frontmatter.get("source_type"):
        return str(frontmatter["source_type"])
    ext = path.suffix.lower()
    if ext in {".md", ".markdown"}:
        return "markdown"
    if ext == ".txt":
        return "txt"
    return "file"


def _merge_metadata(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    combined = {**base}
    combined.update({k: v for k, v in overrides.items() if v is not None})
    return combined


def _normalise_passage_meta(detected: DetectedOsis, hints: list[str] | None) -> dict[str, Any] | None:
    osis_all: list[str] = []
    if hints:
        osis_all.extend(hints)
    osis_all.extend(detected.all)
    if not osis_all:
        return None
    deduped = sorted({ref for ref in osis_all if ref})
    return {"osis_refs_all": deduped}


def _coerce_date(value: Any) -> date | None:
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


def _ensure_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def run_pipeline_for_file(session: Session, path: Path, frontmatter: dict[str, Any] | None = None) -> Document:
    """Execute the file ingestion pipeline synchronously."""

    settings = get_settings()
    raw_bytes = path.read_bytes()
    sha256 = hashlib.sha256(raw_bytes).hexdigest()

    text, parsed_frontmatter = _parse_text_file(path)
    frontmatter = _merge_metadata(parsed_frontmatter, _load_frontmatter(frontmatter))
    source_type = _detect_source_type(path, frontmatter)

    document = Document(
        id=str(uuid4()),
        title=frontmatter.get("title") or path.stem,
        authors=_ensure_list(frontmatter.get("authors")),
        source_url=frontmatter.get("source_url"),
        source_type=source_type,
        collection=frontmatter.get("collection"),
        pub_date=_coerce_date(frontmatter.get("date")),
        channel=frontmatter.get("channel"),
        video_id=frontmatter.get("video_id"),
        duration_seconds=frontmatter.get("duration_seconds"),
        bib_json=frontmatter.get("bib_json"),
        sha256=sha256,
    )

    session.add(document)
    session.flush()

    chunk_hints = _ensure_list(frontmatter.get("osis_refs"))
    chunks = chunk_text(text, max_tokens=settings.max_chunk_tokens)
    passages: list[Passage] = []
    for chunk in chunks:
        detected = detect_osis_references(chunk.text)
        meta = _normalise_passage_meta(detected, chunk_hints)
        passage = Passage(
            document_id=document.id,
            page_no=chunk.page_no,
            start_char=chunk.start_char,
            end_char=chunk.end_char,
            text=chunk.text,
            tokens=len(chunk.text.split()),
            osis_ref=detected.primary or (chunk_hints[0] if chunk_hints else None),
            lexeme=chunk.text.lower(),
            meta=meta,
        )
        session.add(passage)
        passages.append(passage)

    session.commit()

    storage_dir = settings.storage_root / document.id
    storage_dir.mkdir(parents=True, exist_ok=True)
    dest_path = storage_dir / path.name
    shutil.copy(path, dest_path)

    normalized_payload = {
        "document": {
            "id": document.id,
            "title": document.title,
            "source_type": document.source_type,
            "authors": document.authors,
            "collection": document.collection,
            "sha256": document.sha256,
        },
        "passages": [
            {
                "id": passage.id,
                "text": passage.text,
                "osis_ref": passage.osis_ref,
                "meta": passage.meta,
            }
            for passage in passages
        ],
    }

    normalized_path = storage_dir / "normalized.json"
    normalized_path.write_text(json.dumps(normalized_payload, indent=2), encoding="utf-8")

    document.storage_path = str(storage_dir)
    session.add(document)
    session.commit()

    return document


def run_pipeline_for_url(session: Session, url: str, source_type: str | None = None) -> Document:
    """Placeholder for URL ingestion. Currently unsupported in the synchronous pipeline."""

    raise UnsupportedSourceError(f"URL ingestion not yet implemented for {url}")
