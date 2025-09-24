"""Ingestion pipeline orchestration."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from uuid import uuid4

import yaml
from sqlalchemy.orm import Session

from ..core.settings import get_settings
from ..db.models import Document, Passage
from .chunking import Chunk, chunk_text, chunk_transcript
from .osis import DetectedOsis, detect_osis_references
from .parsers import TranscriptSegment, load_transcript, parse_pdf, read_text_file

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
    content = read_text_file(path)
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
    if ext == ".pdf":
        return "pdf"
    if ext in {".vtt", ".webvtt", ".srt"}:
        return "transcript"
    if ext == ".json":
        return "transcript"
    if ext == ".docx":
        return "docx"

    return "file"



def _merge_metadata(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    combined = {**base}
    combined.update({k: v for k, v in overrides.items() if v is not None})
    return combined


def _normalise_passage_meta(
    detected: DetectedOsis,
    hints: list[str] | None,
    *,
    parser: str,
    parser_version: str,
    chunker_version: str,
    chunk_index: int,
    speakers: list[str] | None = None,

) -> dict[str, Any]:
    osis_all: list[str] = []
    if hints:
        osis_all.extend(hints)
    osis_all.extend(detected.all)
    deduped = sorted({ref for ref in osis_all if ref})
    meta: dict[str, Any] = {
        "parser": parser,
        "parser_version": parser_version,
        "chunker_version": chunker_version,
        "chunk_index": chunk_index,
    }
    if deduped:
        meta["osis_refs_all"] = deduped
    if detected.primary:
        meta["primary_osis"] = detected.primary
    if speakers:
        meta["speakers"] = speakers
    return meta


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


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _derive_duration_from_chunks(chunks: list[Chunk]) -> int | None:
    for chunk in reversed(chunks):
        if chunk.t_end is not None:
            return _coerce_int(chunk.t_end)
    return None

def _resolve_fixtures_dir(settings) -> Path | None:
    root = getattr(settings, "fixtures_root", None)
    if not root:
        return None
    path = Path(root)
    if not path.exists():
        return None
    return path


def _load_youtube_transcript(settings, video_id: str) -> tuple[list[TranscriptSegment], Path | None]:
    fixtures_dir = _resolve_fixtures_dir(settings)
    transcript_path: Path | None = None
    if fixtures_dir:
        base = fixtures_dir / "youtube"
        for suffix in (".vtt", ".webvtt", ".json", ".srt"):
            candidate = base / f"{video_id}{suffix}"
            if candidate.exists():
                transcript_path = candidate
                break

    segments: list[TranscriptSegment] = []
    if transcript_path:
        segments = load_transcript(transcript_path)
    else:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
        except ImportError as exc:  # pragma: no cover - defensive fallback
            raise UnsupportedSourceError(
                "youtube-transcript-api not installed and no transcript fixture found"
            ) from exc

        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
        except Exception as exc:  # pragma: no cover - network failure fallback
            raise UnsupportedSourceError(f"Unable to fetch transcript for video {video_id}") from exc

        for item in transcript:
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            start = float(item.get("start", 0.0))
            duration = float(item.get("duration", 0.0))
            segments.append(
                TranscriptSegment(
                    text=text,
                    start=start,
                    end=start + duration,
                )
            )

    if not segments:
        raise UnsupportedSourceError(f"No transcript segments found for {video_id}")
    return segments, transcript_path


def _load_youtube_metadata(settings, video_id: str) -> dict[str, Any]:
    fixtures_dir = _resolve_fixtures_dir(settings)
    if not fixtures_dir:
        return {}
    meta_path = fixtures_dir / "youtube" / f"{video_id}.meta.json"
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _extract_youtube_video_id(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "youtube" in host:
        if parsed.path == "/watch":
            qs = parse_qs(parsed.query)
            vid = qs.get("v", [None])[0]
            if vid:
                return vid
        elif parsed.path.startswith("/shorts/"):
            return parsed.path.split("/shorts/")[1].split("/")[0]
        elif parsed.path.startswith("/") and len(parsed.path.strip("/")) > 0:
            return parsed.path.strip("/")
    if "youtu.be" in host:
        return parsed.path.strip("/")
    raise UnsupportedSourceError(f"Unsupported URL for ingestion: {url}")


def _prepare_text_chunks(text: str, *, settings) -> tuple[list[Chunk], str, str]:
    chunks = chunk_text(text, max_tokens=settings.max_chunk_tokens)
    return chunks, "plain_text", "0.1.0"


def _prepare_pdf_chunks(path: Path, *, settings) -> tuple[list[Chunk], str, str]:
    pages = parse_pdf(path, max_pages=settings.doc_max_pages)
    if not pages:
        raise UnsupportedSourceError("PDF contained no extractable text")
    chunks: list[Chunk] = []
    index = 0
    cursor = 0
    for page in pages:
        page_chunks = chunk_text(page.text, max_tokens=settings.max_chunk_tokens)
        for chunk in page_chunks:
            chunk.page_no = page.page_no
            chunk.index = index
            chunk.start_char += cursor
            chunk.end_char += cursor
            chunks.append(chunk)
            index += 1
        cursor += len(page.text) + 1
    return chunks, "pdfminer", "0.2.0"


def _prepare_transcript_chunks(
    segments: list[TranscriptSegment],
    *,
    settings,
) -> tuple[list[Chunk], str, str]:
    if not segments:
        raise UnsupportedSourceError("Transcript file contained no segments")
    chunks = chunk_transcript(
        segments,
        max_tokens=settings.max_chunk_tokens,
        max_window_seconds=getattr(settings, "transcript_max_window", 40.0),
    )
    return chunks, "transcript", "0.3.0"


def _persist_transcript_document(
    session: Session,
    *,
    chunks: list[Chunk],
    parser: str,
    parser_version: str,
    frontmatter: dict[str, Any],
    settings,
    sha256: str,
    source_type: str,
    title: str,
    source_url: str | None = None,
    channel: str | None = None,
    video_id: str | None = None,
    duration_seconds: Any | None = None,
    transcript_path: Path | None = None,
    audio_path: Path | None = None,
) -> Document:
    document = Document(
        id=str(uuid4()),
        title=title or frontmatter.get("title") or "Transcript",
        authors=_ensure_list(frontmatter.get("authors")),
        source_url=source_url or frontmatter.get("source_url"),
        source_type=source_type,
        collection=frontmatter.get("collection"),
        pub_date=_coerce_date(frontmatter.get("date")),
        channel=channel or frontmatter.get("channel"),
        video_id=video_id or frontmatter.get("video_id"),
        duration_seconds=_coerce_int(duration_seconds)
        or _coerce_int(frontmatter.get("duration_seconds"))
        or _derive_duration_from_chunks(chunks),
        bib_json=frontmatter.get("bib_json"),
        sha256=sha256,
    )

    session.add(document)
    session.flush()

    chunk_hints = _ensure_list(frontmatter.get("osis_refs"))
    passages: list[Passage] = []
    for chunk in chunks:
        detected = detect_osis_references(chunk.text)
        meta = _normalise_passage_meta(
            detected,
            chunk_hints,
            parser=parser,
            parser_version=parser_version,
            chunker_version="0.3.0",
            chunk_index=chunk.index or 0,
            speakers=chunk.speakers,
        )
        osis_value = detected.primary or (chunk_hints[0] if chunk_hints else None)
        passage = Passage(
            document_id=document.id,
            page_no=chunk.page_no,
            t_start=chunk.t_start,
            t_end=chunk.t_end,
            start_char=chunk.start_char,
            end_char=chunk.end_char,
            text=chunk.text,
            tokens=len(chunk.text.split()),
            osis_ref=osis_value,
            lexeme=chunk.text.lower(),
            meta=meta,
        )
        session.add(passage)
        passages.append(passage)

    session.commit()

    storage_dir = settings.storage_root / document.id
    storage_dir.mkdir(parents=True, exist_ok=True)

    artifacts: dict[str, str] = {}
    if transcript_path and transcript_path.exists():
        dest = storage_dir / transcript_path.name
        shutil.copy(transcript_path, dest)
        artifacts["transcript"] = dest.name
    else:
        transcript_json = [
            {
                "text": passage.text,
                "start": passage.t_start,
                "end": passage.t_end,
                "speakers": passage.meta.get("speakers") if passage.meta else None,
            }
            for passage in passages
        ]
        transcript_file = storage_dir / "transcript.json"
        transcript_file.write_text(json.dumps(transcript_json, indent=2), encoding="utf-8")
        artifacts["transcript"] = transcript_file.name

    if audio_path and audio_path.exists():
        audio_dest = storage_dir / audio_path.name
        shutil.copy(audio_path, audio_dest)
        artifacts["audio"] = audio_dest.name

    normalized_payload = {
        "document": {
            "id": document.id,
            "title": document.title,
            "source_type": document.source_type,
            "authors": document.authors,
            "collection": document.collection,
            "channel": document.channel,
            "video_id": document.video_id,
            "sha256": document.sha256,
        },
        "passages": [
            {
                "id": passage.id,
                "text": passage.text,
                "osis_ref": passage.osis_ref,
                "page_no": passage.page_no,
                "t_start": passage.t_start,
                "t_end": passage.t_end,
                "meta": passage.meta,
            }
            for passage in passages
        ],
    }

    if artifacts:
        normalized_payload["artifacts"] = artifacts

    normalized_path = storage_dir / "normalized.json"
    normalized_path.write_text(json.dumps(normalized_payload, indent=2), encoding="utf-8")

    document.storage_path = str(storage_dir)
    session.add(document)
    session.commit()

    return document

def run_pipeline_for_file(session: Session, path: Path, frontmatter: dict[str, Any] | None = None) -> Document:
    """Execute the file ingestion pipeline synchronously."""

    settings = get_settings()
    raw_bytes = path.read_bytes()
    sha256 = hashlib.sha256(raw_bytes).hexdigest()

    frontmatter = _merge_metadata({}, _load_frontmatter(frontmatter))
    source_type = _detect_source_type(path, frontmatter)

    parser = "plain_text"
    parser_version = "0.1.0"
    text_content = ""
    chunks: list[Chunk]

    if source_type in {"markdown", "txt", "file", "docx"}:
        text_content, parsed_frontmatter = _parse_text_file(path)
        frontmatter = _merge_metadata(parsed_frontmatter, frontmatter)
        chunks, parser, parser_version = _prepare_text_chunks(text_content, settings=settings)
    elif source_type == "pdf":
        text_content = ""
        chunks, parser, parser_version = _prepare_pdf_chunks(path, settings=settings)
    elif source_type == "transcript":
        segments = load_transcript(path)
        chunks, parser, parser_version = _prepare_transcript_chunks(segments, settings=settings)
        text_content = " ".join(chunk.text for chunk in chunks)
    else:
        text_content, parsed_frontmatter = _parse_text_file(path)
        frontmatter = _merge_metadata(parsed_frontmatter, frontmatter)
        chunks, parser, parser_version = _prepare_text_chunks(text_content, settings=settings)

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
    passages: list[Passage] = []
    for chunk in chunks:
        detected = detect_osis_references(chunk.text)
        meta = _normalise_passage_meta(
            detected,
            chunk_hints,
            parser=parser,
            parser_version=parser_version,
            chunker_version="0.3.0",
            chunk_index=chunk.index or 0,
            speakers=chunk.speakers,
        )
        osis_value = detected.primary or (chunk_hints[0] if chunk_hints else None)
        passage = Passage(
            document_id=document.id,
            page_no=chunk.page_no,
            t_start=chunk.t_start,
            t_end=chunk.t_end,
            start_char=chunk.start_char,
            end_char=chunk.end_char,
            text=chunk.text,
            tokens=len(chunk.text.split()),
            osis_ref=osis_value,
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
                "page_no": passage.page_no,
                "t_start": passage.t_start,
                "t_end": passage.t_end,
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


def run_pipeline_for_transcript(
    session: Session,
    transcript_path: Path,
    *,
    frontmatter: dict[str, Any] | None = None,
    audio_path: Path | None = None,
) -> Document:
    """Ingest a transcript file and optional audio into the document store."""

    settings = get_settings()
    frontmatter = _merge_metadata({}, _load_frontmatter(frontmatter))

    segments = load_transcript(transcript_path)
    chunks, parser, parser_version = _prepare_transcript_chunks(segments, settings=settings)

    sha_payload = "\n".join(chunk.text for chunk in chunks).encode("utf-8")
    sha256 = hashlib.sha256(sha_payload).hexdigest()

    source_type = str(frontmatter.get("source_type") or "transcript")
    title = frontmatter.get("title") or transcript_path.stem

    return _persist_transcript_document(
        session,
        chunks=chunks,
        parser=parser,
        parser_version=parser_version,
        frontmatter=frontmatter,
        settings=settings,
        sha256=sha256,
        source_type=source_type,
        title=title,
        source_url=frontmatter.get("source_url"),
        channel=frontmatter.get("channel"),
        video_id=frontmatter.get("video_id"),
        duration_seconds=frontmatter.get("duration_seconds"),
        transcript_path=transcript_path,
        audio_path=audio_path,
    )


def run_pipeline_for_url(
    session: Session,
    url: str,
    source_type: str | None = None,
    frontmatter: dict[str, Any] | None = None,
) -> Document:
    """Ingest supported URLs (currently YouTube) into the document store."""

    settings = get_settings()
    resolved_source_type = source_type or "youtube"
    if resolved_source_type != "youtube":
        raise UnsupportedSourceError(f"Unsupported source type for URL ingestion: {resolved_source_type}")

    video_id = _extract_youtube_video_id(url)
    metadata = _load_youtube_metadata(settings, video_id)
    frontmatter = _merge_metadata(metadata, _load_frontmatter(frontmatter))

    segments, transcript_path = _load_youtube_transcript(settings, video_id)
    chunks, parser, parser_version = _prepare_transcript_chunks(segments, settings=settings)

    sha_payload = "\n".join(chunk.text for chunk in chunks).encode("utf-8")
    sha256 = hashlib.sha256(sha_payload).hexdigest()

    return _persist_transcript_document(
        session,
        chunks=chunks,
        parser=parser,
        parser_version=parser_version,
        frontmatter=frontmatter,
        settings=settings,
        sha256=sha256,
        source_type="youtube",
        title=frontmatter.get("title") or f"YouTube Video {video_id}",
        source_url=url,
        channel=frontmatter.get("channel"),
        video_id=video_id,
        duration_seconds=frontmatter.get("duration_seconds"),
        transcript_path=transcript_path,
    )
