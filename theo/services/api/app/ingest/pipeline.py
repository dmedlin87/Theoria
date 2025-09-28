"""Ingestion pipeline orchestration."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import date, datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from ipaddress import ip_address, ip_network
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

import yaml
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.settings import get_settings
from ..creators.verse_perspectives import CreatorVersePerspectiveService
from ..db.models import (
    Creator,
    CreatorClaim,
    Document,
    Passage,
    TranscriptQuote,
    TranscriptSegment,
    Video,
)
from .chunking import Chunk, chunk_text, chunk_transcript
from .embeddings import get_embedding_service, lexical_representation
from .osis import (
    DetectedOsis,
    classify_osis_matches,
    detect_osis_references,
)
from .parsers import (
    ParserResult,
    TranscriptSegment as ParsedTranscriptSegment,
    load_transcript,
    parse_audio_document,
    parse_docx_document,
    parse_html_document,
    parse_pdf_document,
    read_text_file,
)


class UnsupportedSourceError(ValueError):
    """Raised when the pipeline cannot parse an input file."""


_URL_SCHEME_ERROR = "URL scheme is not allowed for ingestion"
_URL_TARGET_ERROR = "URL target is not allowed for ingestion"


def _normalise_host(host: str) -> str:
    return host.strip().lower().rstrip(".")


def _parse_blocked_networks(networks: list[str]) -> list[ip_network]:
    parsed: list[ip_network] = []
    for cidr in networks:
        try:
            parsed.append(ip_network(cidr, strict=False))
        except ValueError:
            continue
    return parsed


def _ensure_url_allowed(settings, url: str) -> None:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise UnsupportedSourceError("URL must include a scheme and host")

    scheme = parsed.scheme.lower()
    blocked_schemes = {item.lower() for item in settings.ingest_url_blocked_schemes}
    if scheme in blocked_schemes:
        raise UnsupportedSourceError(_URL_SCHEME_ERROR)

    allowed_schemes = {item.lower() for item in settings.ingest_url_allowed_schemes}
    if allowed_schemes and scheme not in allowed_schemes:
        raise UnsupportedSourceError(_URL_SCHEME_ERROR)

    if parsed.username or parsed.password:
        raise UnsupportedSourceError(_URL_TARGET_ERROR)

    host = parsed.hostname
    if host is None:
        raise UnsupportedSourceError("URL must include a hostname")

    normalised_host = _normalise_host(host)
    allowed_hosts = {item.lower() for item in settings.ingest_url_allowed_hosts}
    blocked_hosts = {item.lower() for item in settings.ingest_url_blocked_hosts}
    host_is_allowed = normalised_host in allowed_hosts if allowed_hosts else False

    if allowed_hosts and not host_is_allowed:
        raise UnsupportedSourceError(_URL_TARGET_ERROR)

    if normalised_host in blocked_hosts and not host_is_allowed:
        raise UnsupportedSourceError(_URL_TARGET_ERROR)

    try:
        ip = ip_address(normalised_host)
    except ValueError:
        ip = None

    if ip is not None and not host_is_allowed:
        if settings.ingest_url_block_private_networks and (
            ip.is_loopback or ip.is_private or ip.is_reserved or ip.is_link_local
        ):
            raise UnsupportedSourceError(_URL_TARGET_ERROR)

        for network in _parse_blocked_networks(settings.ingest_url_blocked_ip_networks):
            if ip in network:
                raise UnsupportedSourceError(_URL_TARGET_ERROR)
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


def _merge_metadata(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    combined = {**base}
    combined.update({k: v for k, v in overrides.items() if v is not None})
    return combined


def _refresh_creator_verse_rollups(
    session: Session, segments: list[TranscriptSegment]
) -> None:
    """Refresh cached creator verse rollups impacted by *segments*."""

    osis_refs: set[str] = set()
    for segment in segments:
        if segment.osis_refs:
            osis_refs.update(segment.osis_refs)

    if not osis_refs:
        return

    settings = get_settings()
    sorted_refs = sorted(osis_refs)
    if getattr(settings, "creator_verse_rollups_async_refresh", False):
        try:
            from ..workers import tasks as worker_tasks

            task = getattr(worker_tasks, "refresh_creator_verse_rollups", None)
            if task:
                maybe_delay = getattr(task, "delay", None)
                if callable(maybe_delay):
                    maybe_delay(sorted_refs)
                else:
                    task(sorted_refs)
                return
        except Exception:
            # Fall back to in-process refresh if the broker is unavailable.
            pass

    service = CreatorVersePerspectiveService(session)
    service.refresh_many(sorted_refs)


def _serialise_frontmatter(frontmatter: dict[str, Any]) -> str:
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


def _coerce_datetime(value: Any) -> datetime | None:
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


def _ensure_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _normalise_guardrail_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalise_guardrail_collection(value: Any) -> list[str] | None:
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


def _safe_storage_name(name: str, *, fallback: str) -> str:
    """Return a safe filename for persisted artifacts.

    The candidate is normalised to its basename and values that would resolve
    to the current or parent directory are rejected. When the provided name is
    unsafe we fall back to ``fallback`` (which should originate from a trusted
    source such as the upload path) before raising ``ValueError`` if no safe
    option remains.
    """

    candidate = Path(name).name
    if candidate in {"", ".", ".."}:
        candidate = Path(fallback).name

    if candidate in {"", ".", ".."}:
        raise ValueError("artifact filename resolves outside storage directory")

    return candidate


def _extract_guardrail_profile(
    frontmatter: dict[str, Any]
) -> tuple[str | None, list[str] | None]:
    tradition = _normalise_guardrail_value(frontmatter.get("theological_tradition"))
    topic_domains = _normalise_guardrail_collection(
        frontmatter.get("topic_domains") or frontmatter.get("topic_domain")
    )

    tag_sources: list[str] = []
    for key in ("admin_tags", "tags"):
        entries = _ensure_list(frontmatter.get(key)) or []
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


def _get_or_create_creator(
    session: Session,
    *,
    name: str | None,
    channel: str | None,
    bio: str | None,
    tags: list[str] | None,
) -> Creator | None:
    if not name:
        return None
    cleaned = name.strip()
    if not cleaned:
        return None

    creator = (
        session.query(Creator)
        .filter(func.lower(Creator.name) == cleaned.lower())
        .one_or_none()
    )
    if creator is None:
        creator = Creator(name=cleaned, channel=channel, bio=bio, tags=tags or None)
        session.add(creator)
        session.flush()
        return creator

    updated = False
    if channel and not creator.channel:
        creator.channel = channel
        updated = True
    if bio and not creator.bio:
        creator.bio = bio
        updated = True
    if tags:
        existing = set(creator.tags or [])
        merged = sorted(existing | {tag for tag in tags if tag})
        if merged and merged != (creator.tags or []):
            creator.tags = merged
            updated = True
    if updated:
        session.add(creator)
        session.flush()
    return creator


def _get_or_create_video(
    session: Session,
    *,
    creator: Creator | None,
    document: Document,
    video_identifier: str | None,
    title: str | None,
    url: str | None,
    published_at: Any,
    duration_seconds: int | None,
    license: str | None,
    meta: Any,
) -> Video | None:
    if not video_identifier and not document:
        return None

    video: Video | None = None
    if video_identifier:
        video = (
            session.query(Video)
            .filter(Video.video_id == video_identifier)
            .one_or_none()
        )
    if video is None:
        video = (
            session.query(Video).filter(Video.document_id == document.id).one_or_none()
        )

    published_dt = _coerce_datetime(published_at)
    normalized_meta = meta if isinstance(meta, dict) else None

    if video is None:
        video = Video(
            video_id=video_identifier,
            creator_id=creator.id if creator else None,
            document_id=document.id,
            title=title,
            url=url,
            published_at=published_dt,
            duration_seconds=duration_seconds,
            license=license,
            meta=normalized_meta,
        )
        session.add(video)
        session.flush()
        return video

    changed = False
    if creator and video.creator_id is None:
        video.creator_id = creator.id
        changed = True
    if title and not video.title:
        video.title = title
        changed = True
    if url and not video.url:
        video.url = url
        changed = True
    if published_dt and not video.published_at:
        video.published_at = published_dt
        changed = True
    if duration_seconds and not video.duration_seconds:
        video.duration_seconds = duration_seconds
        changed = True
    if license and not video.license:
        video.license = license
        changed = True
    if normalized_meta and not video.meta:
        video.meta = normalized_meta
        changed = True
    if video_identifier and not video.video_id:
        video.video_id = video_identifier
        changed = True
    if changed:
        session.add(video)
        session.flush()
    if video.document_id is None:
        video.document_id = document.id
        session.add(video)
        session.flush()
    return video


def _build_source_ref(
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


def _truncate(text: str, limit: int = 280) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _collect_topics(document: Document, frontmatter: dict[str, Any]) -> list[str]:
    topics: list[str] = []
    doc_topics = document.topics
    if isinstance(doc_topics, dict):
        topics.extend(doc_topics.get("all") or [])
    elif isinstance(doc_topics, list):
        topics.extend(str(item) for item in doc_topics if item)
    additional = _ensure_list(frontmatter.get("topics")) or []
    for item in additional:
        if item not in topics:
            topics.append(item)
    return [topic for topic in (topic.strip() for topic in topics) if topic]


def _normalise_topics_field(*candidates: Any) -> dict | None:
    values: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        items = _ensure_list(candidate) or []
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
    """Return the most suitable fixtures directory for the runtime settings."""

    candidates: list[Path] = []

    root = getattr(settings, "fixtures_root", None)
    if root:
        path = Path(root)
        if not path.is_absolute():
            project_root = Path(__file__).resolve().parents[5]
            path = (project_root / path).resolve()
        candidates.append(path)

    # Always fall back to the repository fixtures directory so tests that run
    # without the optional datasets present still exercise the offline flows.
    candidates.append(Path(__file__).resolve().parents[5] / "fixtures")

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _load_youtube_transcript(
    settings, video_id: str
) -> tuple[list[ParsedTranscriptSegment], Path | None]:
    fixtures_dir = _resolve_fixtures_dir(settings)
    transcript_path: Path | None = None
    if fixtures_dir:
        base = fixtures_dir / "youtube"
        for suffix in (".vtt", ".webvtt", ".json", ".srt"):
            candidate = base / f"{video_id}{suffix}"
            if candidate.exists():
                transcript_path = candidate
                break

    segments: list[ParsedTranscriptSegment] = []
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
            raise UnsupportedSourceError(
                f"Unable to fetch transcript for video {video_id}"
            ) from exc

        for item in transcript:
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            start = float(item.get("start", 0.0))
            duration = float(item.get("duration", 0.0))
            segments.append(
                ParsedTranscriptSegment(
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


def _is_youtube_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return "youtube" in host or "youtu.be" in host


def _prepare_text_chunks(text: str, *, settings) -> ParserResult:

    chunks = chunk_text(text, max_tokens=settings.max_chunk_tokens)
    return ParserResult(
        text=text, chunks=chunks, parser="plain_text", parser_version="0.1.0"
    )


def _prepare_pdf_chunks(path: Path, *, settings) -> ParserResult:
    result = parse_pdf_document(
        path,
        max_pages=settings.doc_max_pages,
        max_tokens=settings.max_chunk_tokens,
    )
    if not result.chunks:
        raise UnsupportedSourceError("PDF contained no extractable text")
    return result


def _prepare_transcript_chunks(
    segments: list[ParsedTranscriptSegment],
    *,
    settings,
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


class _HTMLMetadataParser(HTMLParser):
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


class _HTMLTextExtractor(HTMLParser):
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
        "li",
        "main",
        "nav",
        "p",
        "pre",
        "section",
        "summary",
        "ul",
        "ol",
    }

    _SKIP_TAGS = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        if lower in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if lower == "br":
            self._emit_newline()
        elif lower in self._BLOCK_TAGS:
            self._emit_paragraph_break()

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower in self._SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if lower in self._BLOCK_TAGS and lower != "br":
            self._emit_paragraph_break()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = unescape(data)
        if not text.strip():
            return
        if self._parts and not self._parts[-1].endswith((" ", "\n")):
            self._parts.append(" ")
        self._parts.append(text.strip())

    def _emit_newline(self) -> None:
        if not self._parts or self._parts[-1].endswith("\n"):
            return
        self._parts.append("\n")

    def _emit_paragraph_break(self) -> None:
        if not self._parts:
            return
        if self._parts[-1].endswith("\n\n"):
            return
        if not self._parts[-1].endswith("\n"):
            self._parts.append("\n")
        self._parts.append("\n")

    def get_text(self) -> str:
        joined = "".join(self._parts)
        lines = [line.strip() for line in joined.splitlines()]
        filtered = [line for line in lines if line]
        return "\n\n".join(filtered).strip()


def _parse_html_metadata(html: str) -> dict[str, str | None]:
    parser = _HTMLMetadataParser()
    parser.feed(html)
    parser.close()
    return {"title": parser.title, "canonical_url": parser.canonical_url}


def _html_to_text(html: str) -> str:
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    extractor.close()
    return extractor.get_text()


def _fetch_web_document(settings, url: str) -> tuple[str, dict[str, str | None]]:
    _ensure_url_allowed(settings, url)
    request = Request(url, headers={"User-Agent": settings.user_agent})
    try:
        with urlopen(request) as response:
            final_url = response.geturl()
            _ensure_url_allowed(settings, final_url)
            raw = response.read()
            encoding = response.headers.get_content_charset() or "utf-8"
            try:
                html = raw.decode(encoding, errors="replace")
            except LookupError:
                html = raw.decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise UnsupportedSourceError(f"Unable to fetch URL: {url}") from exc

    metadata = _parse_html_metadata(html)
    metadata.setdefault("canonical_url", final_url)
    metadata.setdefault("title", None)
    metadata["source_url"] = metadata.get("canonical_url") or final_url
    metadata["final_url"] = final_url
    return html, metadata


def run_pipeline_for_file(
    session: Session, path: Path, frontmatter: dict[str, Any] | None = None
) -> Document:
    """Execute the file ingestion pipeline synchronously."""

    settings = get_settings()
    raw_bytes = path.read_bytes()
    sha256 = hashlib.sha256(raw_bytes).hexdigest()

    frontmatter = _merge_metadata({}, _load_frontmatter(frontmatter))
    source_type = _detect_source_type(path, frontmatter)

    parser_result: ParserResult | None = None
    text_content = ""

    if source_type in {"markdown", "txt", "file"}:
        text_content, parsed_frontmatter = _parse_text_file(path)
        frontmatter = _merge_metadata(parsed_frontmatter, frontmatter)
        parser_result = _prepare_text_chunks(text_content, settings=settings)
    elif source_type == "docx":
        parser_result = parse_docx_document(path, max_tokens=settings.max_chunk_tokens)
        frontmatter = _merge_metadata(parser_result.metadata, frontmatter)
        text_content = parser_result.text
    elif source_type == "html":
        parser_result = parse_html_document(path, max_tokens=settings.max_chunk_tokens)
        frontmatter = _merge_metadata(parser_result.metadata, frontmatter)
        text_content = parser_result.text
    elif source_type == "pdf":
        parser_result = _prepare_pdf_chunks(path, settings=settings)
        text_content = parser_result.text
    elif source_type == "transcript":
        segments = load_transcript(path)
        parser_result = _prepare_transcript_chunks(segments, settings=settings)
        text_content = parser_result.text
    elif source_type == "audio":
        parser_result = parse_audio_document(
            path,
            max_tokens=settings.max_chunk_tokens,
            settings=settings,
            frontmatter=frontmatter,
        )
        frontmatter = _merge_metadata(parser_result.metadata, frontmatter)
        text_content = parser_result.text
    else:
        text_content, parsed_frontmatter = _parse_text_file(path)
        frontmatter = _merge_metadata(parsed_frontmatter, frontmatter)
        parser_result = _prepare_text_chunks(text_content, settings=settings)

    if parser_result is None:
        raise UnsupportedSourceError(f"Unable to parse source type {source_type}")

    if source_type == "transcript":
        return _persist_transcript_document(
            session,
            chunks=parser_result.chunks,
            parser=parser_result.parser,
            parser_version=parser_result.parser_version,
            frontmatter=frontmatter,
            settings=settings,
            sha256=sha256,
            source_type="transcript",
            title=frontmatter.get("title") or path.stem,
            source_url=frontmatter.get("source_url"),
            transcript_path=path,
            transcript_filename=path.name,
        )

    return _persist_text_document(
        session,
        chunks=parser_result.chunks,
        parser=parser_result.parser,
        parser_version=parser_result.parser_version,
        frontmatter=frontmatter,
        settings=settings,
        sha256=sha256,
        source_type=source_type,
        title=frontmatter.get("title") or path.stem,
        source_url=frontmatter.get("source_url"),
        text_content=text_content,
        original_path=path,
    )


def _persist_text_document(
    session: Session,
    *,
    chunks: list[Chunk],
    parser: str,
    parser_version: str,
    frontmatter: dict[str, Any],
    settings,
    sha256: str,
    source_type: str,
    title: str | None,
    source_url: str | None,
    text_content: str,
    original_path: Path | None = None,
    raw_content: str | None = None,
    raw_filename: str | None = None,
) -> Document:
    tradition, topic_domains = _extract_guardrail_profile(frontmatter)

    document = Document(
        id=str(uuid4()),
        title=title or frontmatter.get("title") or "Document",
        authors=_ensure_list(frontmatter.get("authors")),
        doi=frontmatter.get("doi"),
        source_url=source_url or frontmatter.get("source_url"),
        source_type=source_type,
        collection=frontmatter.get("collection"),
        pub_date=_coerce_date(frontmatter.get("date")),
        year=_coerce_int(frontmatter.get("year") or frontmatter.get("pub_year")),
        venue=frontmatter.get("venue"),
        abstract=frontmatter.get("abstract"),
        topics=_normalise_topics_field(
            frontmatter.get("topics"),
            frontmatter.get("concepts"),
        ),
        channel=frontmatter.get("channel"),
        video_id=frontmatter.get("video_id"),
        duration_seconds=_coerce_int(frontmatter.get("duration_seconds")),
        bib_json=frontmatter.get("bib_json"),
        theological_tradition=tradition,
        topic_domains=topic_domains,
        sha256=sha256,
    )

    session.add(document)
    session.flush()

    creator_tags = _ensure_list(frontmatter.get("creator_tags"))
    creator_profile = _get_or_create_creator(
        session,
        name=frontmatter.get("creator"),
        channel=document.channel,
        bio=frontmatter.get("creator_bio"),
        tags=creator_tags,
    )

    video_record = _get_or_create_video(
        session,
        creator=creator_profile,
        document=document,
        video_identifier=document.video_id,
        title=document.title,
        url=document.source_url or frontmatter.get("url"),
        published_at=frontmatter.get("published_at"),
        duration_seconds=document.duration_seconds,
        license=frontmatter.get("license") or frontmatter.get("video_license"),
        meta=frontmatter.get("video_meta"),
    )

    chunk_hints = _ensure_list(frontmatter.get("osis_refs"))
    embedding_service = get_embedding_service()
    embeddings = embedding_service.embed([chunk.text for chunk in chunks])

    passages: list[Passage] = []
    segments: list[TranscriptSegment] = []
    for idx, chunk in enumerate(chunks):
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
        if tradition:
            meta.setdefault("theological_tradition", tradition)
        if topic_domains:
            meta.setdefault("topic_domains", topic_domains)
        osis_value = detected.primary or (chunk_hints[0] if chunk_hints else None)
        embedding = embeddings[idx] if idx < len(embeddings) else None
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
            embedding=embedding,
            lexeme=lexical_representation(session, chunk.text),
            meta=meta,
        )
        session.add(passage)
        passages.append(passage)

        osis_all: list[str] = []
        if meta.get("osis_refs_all"):
            osis_all.extend(meta["osis_refs_all"])
        if osis_value:
            osis_all.append(osis_value)
        normalized_refs = sorted({ref for ref in osis_all if ref})

        segment = TranscriptSegment(
            document_id=document.id,
            video_id=video_record.id if video_record else None,
            t_start=chunk.t_start,
            t_end=chunk.t_end,
            text=chunk.text,
            primary_osis=osis_value,
            osis_refs=normalized_refs or None,
            topics=None,
            entities=None,
        )
        session.add(segment)
        segments.append(segment)

    session.flush()

    topics = _collect_topics(document, frontmatter)
    stance_overrides_raw = frontmatter.get("creator_stances") or {}
    stance_overrides: dict[str, str] = {}
    if isinstance(stance_overrides_raw, dict):
        for key, value in stance_overrides_raw.items():
            key_clean = str(key).strip().lower()
            value_clean = str(value).strip()
            if key_clean and value_clean:
                stance_overrides[key_clean] = value_clean

    confidence_default: float | None
    raw_confidence = frontmatter.get("creator_confidence")
    try:
        confidence_default = float(raw_confidence) if raw_confidence is not None else None
    except (TypeError, ValueError):
        confidence_default = None

    quote_identifier = (
        video_record.video_id
        if video_record and video_record.video_id
        else document.video_id
    )
    quote_source_url = (
        (video_record.url if video_record else None)
        or document.source_url
        or frontmatter.get("url")
    )

    for segment in segments:
        if segment.osis_refs:
            quote = TranscriptQuote(
                video_id=video_record.id if video_record else None,
                segment_id=segment.id,
                quote_md=_truncate(segment.text),
                osis_refs=segment.osis_refs,
                source_ref=_build_source_ref(
                    quote_identifier, quote_source_url, segment.t_start
                ),
                salience=1.0,
            )
            session.add(quote)

    if creator_profile and topics:
        for segment in segments:
            if not segment.osis_refs:
                continue
            for topic in topics:
                stance = stance_overrides.get(topic.lower(), "unknown")
                claim = CreatorClaim(
                    creator_id=creator_profile.id,
                    video_id=video_record.id if video_record else None,
                    segment_id=segment.id,
                    topic=topic,
                    stance=stance,
                    claim_md=_truncate(segment.text, limit=600),
                    confidence=(
                        confidence_default if confidence_default is not None else 0.5
                    ),
                )
                session.add(claim)

    session.commit()

    _refresh_creator_verse_rollups(session, segments)

    storage_dir = settings.storage_root / document.id
    storage_dir.mkdir(parents=True, exist_ok=True)

    artifacts: dict[str, str] = {}

    if frontmatter:
        frontmatter_path = storage_dir / "frontmatter.json"
        frontmatter_path.write_text(
            _serialise_frontmatter(frontmatter) + "\n", encoding="utf-8"
        )
        artifacts.setdefault("frontmatter", frontmatter_path.name)

    if original_path and original_path.exists():
        dest_path = storage_dir / original_path.name
        shutil.copy(original_path, dest_path)
        artifacts["source"] = dest_path.name

    content_path = storage_dir / "content.txt"
    content_path.write_text(text_content, encoding="utf-8")
    artifacts["content"] = content_path.name

    if raw_content is not None:
        raw_name = raw_filename or "source.html"
        raw_path = storage_dir / raw_name
        raw_path.write_text(raw_content, encoding="utf-8")
        artifacts["raw"] = raw_path.name

    normalized_payload = {
        "document": {
            "id": document.id,
            "title": document.title,
            "source_type": document.source_type,
            "source_url": document.source_url,
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
        "segments": [
            {
                "id": segment.id,
                "text": segment.text,
                "primary_osis": segment.primary_osis,
                "osis_refs": segment.osis_refs,
                "t_start": segment.t_start,
                "t_end": segment.t_end,
            }
            for segment in segments
        ],
    }

    if artifacts:
        normalized_payload["artifacts"] = artifacts

    normalized_path = storage_dir / "normalized.json"
    normalized_path.write_text(
        json.dumps(normalized_payload, indent=2), encoding="utf-8"
    )

    document.storage_path = str(storage_dir)
    session.add(document)
    session.commit()

    return document


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
    transcript_filename: str | None = None,
    audio_filename: str | None = None,
) -> Document:
    tradition, topic_domains = _extract_guardrail_profile(frontmatter)

    document = Document(
        id=str(uuid4()),
        title=title or frontmatter.get("title") or "Transcript",
        authors=_ensure_list(frontmatter.get("authors")),
        doi=frontmatter.get("doi"),
        source_url=source_url or frontmatter.get("source_url"),
        source_type=source_type,
        collection=frontmatter.get("collection"),
        pub_date=_coerce_date(frontmatter.get("date")),
        year=_coerce_int(frontmatter.get("year") or frontmatter.get("pub_year")),
        venue=frontmatter.get("venue"),
        abstract=frontmatter.get("abstract"),
        topics=_normalise_topics_field(
            frontmatter.get("topics"),
            frontmatter.get("concepts"),
        ),
        channel=channel or frontmatter.get("channel"),
        video_id=video_id or frontmatter.get("video_id"),
        duration_seconds=_coerce_int(duration_seconds)
        or _coerce_int(frontmatter.get("duration_seconds"))
        or _derive_duration_from_chunks(chunks),
        bib_json=frontmatter.get("bib_json"),
        theological_tradition=tradition,
        topic_domains=topic_domains,
        sha256=sha256,
    )

    session.add(document)
    session.flush()

    creator_tags = _ensure_list(frontmatter.get("creator_tags"))
    creator_profile = _get_or_create_creator(
        session,
        name=frontmatter.get("creator"),
        channel=document.channel,
        bio=frontmatter.get("creator_bio"),
        tags=creator_tags,
    )

    video_record = _get_or_create_video(
        session,
        creator=creator_profile,
        document=document,
        video_identifier=document.video_id,
        title=document.title,
        url=document.source_url or frontmatter.get("url"),
        published_at=frontmatter.get("published_at"),
        duration_seconds=document.duration_seconds,
        license=frontmatter.get("license") or frontmatter.get("video_license"),
        meta=frontmatter.get("video_meta"),
    )

    chunk_hints = _ensure_list(frontmatter.get("osis_refs"))
    embedding_service = get_embedding_service()
    embeddings = embedding_service.embed([chunk.text for chunk in chunks])

    passages: list[Passage] = []
    segments: list[TranscriptSegment] = []
    for idx, chunk in enumerate(chunks):
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
        if tradition:
            meta.setdefault("theological_tradition", tradition)
        if topic_domains:
            meta.setdefault("topic_domains", topic_domains)
        osis_value = detected.primary or (chunk_hints[0] if chunk_hints else None)
        embedding = embeddings[idx] if idx < len(embeddings) else None
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
            embedding=embedding,
            lexeme=lexical_representation(session, chunk.text),
            meta=meta,
        )
        session.add(passage)
        passages.append(passage)

        osis_all: list[str] = []
        if meta.get("osis_refs_all"):
            osis_all.extend(meta["osis_refs_all"])
        if osis_value:
            osis_all.append(osis_value)
        normalized_refs = sorted({ref for ref in osis_all if ref})

        segment = TranscriptSegment(
            document_id=document.id,
            video_id=video_record.id if video_record else None,
            t_start=chunk.t_start,
            t_end=chunk.t_end,
            text=chunk.text,
            primary_osis=osis_value,
            osis_refs=normalized_refs or None,
            topics=None,
            entities=None,
        )
        session.add(segment)
        segments.append(segment)

    session.flush()

    topics = _collect_topics(document, frontmatter)
    stance_overrides_raw = frontmatter.get("creator_stances") or {}
    stance_overrides: dict[str, str] = {}
    if isinstance(stance_overrides_raw, dict):
        for key, value in stance_overrides_raw.items():
            key_clean = str(key).strip().lower()
            value_clean = str(value).strip()
            if key_clean and value_clean:
                stance_overrides[key_clean] = value_clean

    confidence_default: float | None
    raw_confidence = frontmatter.get("creator_confidence")
    if raw_confidence is not None:
        try:
            confidence_default = float(raw_confidence)
        except (TypeError, ValueError):
            confidence_default = None
    else:
        confidence_default = None

    quote_identifier = (
        video_record.video_id
        if video_record and video_record.video_id
        else document.video_id
    )
    quote_source_url = (
        (video_record.url if video_record else None)
        or document.source_url
        or frontmatter.get("url")
    )

    for segment in segments:
        if segment.osis_refs:
            quote = TranscriptQuote(
                video_id=video_record.id if video_record else None,
                segment_id=segment.id,
                quote_md=_truncate(segment.text),
                osis_refs=segment.osis_refs,
                source_ref=_build_source_ref(
                    quote_identifier, quote_source_url, segment.t_start
                ),
                salience=1.0,
            )
            session.add(quote)

    if creator_profile and topics:
        for segment in segments:
            if not segment.osis_refs:
                continue
            for topic in topics:
                stance = stance_overrides.get(topic.lower(), "unknown")
                claim = CreatorClaim(
                    creator_id=creator_profile.id,
                    video_id=video_record.id if video_record else None,
                    segment_id=segment.id,
                    topic=topic,
                    stance=stance,
                    claim_md=_truncate(segment.text, limit=600),
                    confidence=(
                        confidence_default if confidence_default is not None else 0.5
                    ),
                )
                session.add(claim)

    session.commit()

    storage_dir = settings.storage_root / document.id
    storage_dir.mkdir(parents=True, exist_ok=True)

    artifacts: dict[str, str] = {}

    if frontmatter:
        frontmatter_path = storage_dir / "frontmatter.json"
        frontmatter_path.write_text(
            _serialise_frontmatter(frontmatter) + "\n", encoding="utf-8"
        )
        artifacts.setdefault("frontmatter", frontmatter_path.name)

    if transcript_path and transcript_path.exists():
        dest_name = _safe_storage_name(
            transcript_filename or transcript_path.name,
            fallback=transcript_path.name,
        )
        dest = storage_dir / dest_name
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
        transcript_file.write_text(
            json.dumps(transcript_json, indent=2), encoding="utf-8"
        )
        artifacts["transcript"] = transcript_file.name

    if audio_path and audio_path.exists():
        audio_name = _safe_storage_name(
            audio_filename or audio_path.name,
            fallback=audio_path.name,
        )
        audio_dest = storage_dir / audio_name
        shutil.copy(audio_path, audio_dest)
        artifacts["audio"] = audio_dest.name

    content_text = "\n\n".join(passage.text for passage in passages)
    if content_text:
        content_path = storage_dir / "content.txt"
        content_path.write_text(content_text, encoding="utf-8")
        artifacts.setdefault("content", content_path.name)

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
        "segments": [
            {
                "id": segment.id,
                "text": segment.text,
                "primary_osis": segment.primary_osis,
                "osis_refs": segment.osis_refs,
                "t_start": segment.t_start,
                "t_end": segment.t_end,
            }
            for segment in segments
        ],
    }

    if artifacts:
        normalized_payload["artifacts"] = artifacts

    normalized_path = storage_dir / "normalized.json"
    normalized_path.write_text(
        json.dumps(normalized_payload, indent=2), encoding="utf-8"
    )

    document.storage_path = str(storage_dir)
    session.add(document)
    session.commit()

    return document


def run_pipeline_for_url(
    session: Session,
    url: str,
    source_type: str | None = None,
    frontmatter: dict[str, Any] | None = None,
) -> Document:
    """Ingest supported URLs into the document store."""

    settings = get_settings()
    resolved_source_type = source_type or (
        "youtube" if _is_youtube_url(url) else "web_page"
    )

    if resolved_source_type != "youtube":
        _ensure_url_allowed(settings, url)

    if resolved_source_type == "youtube":
        video_id = _extract_youtube_video_id(url)
        metadata = _load_youtube_metadata(settings, video_id)
        merged_frontmatter = _merge_metadata(metadata, _load_frontmatter(frontmatter))

        segments, transcript_path = _load_youtube_transcript(settings, video_id)
        parser_result = _prepare_transcript_chunks(segments, settings=settings)
        sha_payload = "\n".join(chunk.text for chunk in parser_result.chunks).encode(
            "utf-8"
        )
        sha256 = hashlib.sha256(sha_payload).hexdigest()

        return _persist_transcript_document(
            session,
            chunks=parser_result.chunks,
            parser=parser_result.parser,
            parser_version=parser_result.parser_version,
            frontmatter=merged_frontmatter,
            settings=settings,
            sha256=sha256,
            source_type="youtube",
            title=merged_frontmatter.get("title")
            or metadata.get("title")
            or f"YouTube Video {video_id}",
            source_url=merged_frontmatter.get("source_url") or url,
            channel=merged_frontmatter.get("channel") or metadata.get("channel"),
            video_id=video_id,
            duration_seconds=merged_frontmatter.get("duration_seconds")
            or metadata.get("duration_seconds"),
            transcript_path=transcript_path,
            transcript_filename=(transcript_path.name if transcript_path else None),
        )

    if resolved_source_type not in {"web_page", "html", "website"}:
        raise UnsupportedSourceError(
            (
                "Unsupported source type for URL ingestion: "
                f"{resolved_source_type}. Supported types are: "
                "youtube, web_page, html, website"
            )
        )

    html, metadata = _fetch_web_document(settings, url)
    text_content = _html_to_text(html)
    if not text_content:
        raise UnsupportedSourceError("Fetched HTML did not contain extractable text")

    merged_frontmatter = _merge_metadata(metadata, _load_frontmatter(frontmatter))
    parser_result = _prepare_text_chunks(text_content, settings=settings)
    sha_payload = "\n".join(chunk.text for chunk in parser_result.chunks).encode(
        "utf-8"
    )
    sha256 = hashlib.sha256(sha_payload).hexdigest()

    return _persist_text_document(
        session,
        chunks=parser_result.chunks,
        parser=parser_result.parser,
        parser_version=parser_result.parser_version,
        frontmatter=merged_frontmatter,
        settings=settings,
        sha256=sha256,
        source_type="web_page",
        title=merged_frontmatter.get("title") or metadata.get("title") or url,
        source_url=merged_frontmatter.get("source_url")
        or metadata.get("canonical_url")
        or url,
        text_content=parser_result.text,
        raw_content=html,
        raw_filename="source.html",
    )


def run_pipeline_for_transcript(
    session: Session,
    transcript_path: Path,
    *,
    frontmatter: dict[str, Any] | None = None,
    audio_path: Path | None = None,
    transcript_filename: str | None = None,
    audio_filename: str | None = None,
) -> Document:
    """Ingest a transcript file and optional audio into the document store."""

    settings = get_settings()
    frontmatter = _merge_metadata({}, _load_frontmatter(frontmatter))

    segments = load_transcript(transcript_path)
    parser_result = _prepare_transcript_chunks(segments, settings=settings)

    sha_payload = "\n".join(chunk.text for chunk in parser_result.chunks).encode(
        "utf-8"
    )
    sha256 = hashlib.sha256(sha_payload).hexdigest()

    source_type = str(frontmatter.get("source_type") or "transcript")
    title = frontmatter.get("title") or transcript_path.stem

    return _persist_transcript_document(
        session,
        chunks=parser_result.chunks,
        parser=parser_result.parser,
        parser_version=parser_result.parser_version,
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
        transcript_filename=transcript_filename or transcript_path.name,
        audio_filename=audio_filename,
    )
