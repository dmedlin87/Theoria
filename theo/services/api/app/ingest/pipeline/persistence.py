"""Persistence layer for the ingestion pipeline."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
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
from ..embeddings import get_embedding_service, lexical_representation
from ..osis import detect_osis_references
from ..sanitizer import sanitize_passage_text
from .exceptions import UnsupportedSourceError
from .metadata import (
    collect_topics,
    coerce_date,
    coerce_datetime,
    coerce_int,
    derive_duration_from_chunks,
    ensure_list,
    extract_guardrail_profile,
    normalise_passage_meta,
    normalise_source_url,
    normalise_topics_field,
    serialise_frontmatter,
)


def ensure_unique_document_sha(session: Session, sha256: str | None) -> None:
    """Raise if *sha256* already exists for another document."""

    if not sha256:
        return

    existing = (
        session.query(Document.id)
        .filter(Document.sha256 == sha256)
        .first()
    )
    if existing is not None:
        raise UnsupportedSourceError("Document already ingested")


def refresh_creator_verse_rollups(
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
        except Exception:  # pragma: no cover - defensive fallback
            pass

    service = CreatorVersePerspectiveService(session)
    service.refresh_many(sorted_refs)


def safe_storage_name(name: str, *, fallback: str) -> str:
    """Return a safe filename for persisted artifacts."""

    candidate = Path(name).name
    if candidate in {"", ".", ".."}:
        candidate = Path(fallback).name

    if candidate in {"", ".", ".."}:
        raise ValueError("artifact filename resolves outside storage directory")

    return candidate


def get_or_create_creator(
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


def get_or_create_video(
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

    published_dt = coerce_datetime(published_at)
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


def persist_text_document(
    session: Session,
    *,
    chunks,
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
    embedding_service=None,
) -> Document:
    tradition, topic_domains = extract_guardrail_profile(frontmatter)

    ensure_unique_document_sha(session, sha256)

    normalised_source_url = normalise_source_url(
        source_url or frontmatter.get("source_url")
    )

    document = Document(
        id=str(uuid4()),
        title=title or frontmatter.get("title") or "Document",
        authors=ensure_list(frontmatter.get("authors")),
        doi=frontmatter.get("doi"),
        source_url=normalised_source_url,
        source_type=source_type,
        collection=frontmatter.get("collection"),
        pub_date=coerce_date(frontmatter.get("date")),
        year=coerce_int(frontmatter.get("year") or frontmatter.get("pub_year")),
        venue=frontmatter.get("venue"),
        abstract=frontmatter.get("abstract"),
        topics=normalise_topics_field(
            frontmatter.get("topics"),
            frontmatter.get("concepts"),
        ),
        channel=frontmatter.get("channel"),
        video_id=frontmatter.get("video_id"),
        duration_seconds=coerce_int(frontmatter.get("duration_seconds")),
        bib_json=frontmatter.get("bib_json"),
        theological_tradition=tradition,
        topic_domains=topic_domains,
        sha256=sha256,
    )

    try:
        session.add(document)
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise UnsupportedSourceError("Document already ingested") from exc

    creator_tags = ensure_list(frontmatter.get("creator_tags"))
    creator_profile = get_or_create_creator(
        session,
        name=frontmatter.get("creator"),
        channel=document.channel,
        bio=frontmatter.get("creator_bio"),
        tags=creator_tags,
    )

    video_record = get_or_create_video(
        session,
        creator=creator_profile,
        document=document,
        video_identifier=document.video_id,
        title=document.title,
        url=document.source_url or normalise_source_url(frontmatter.get("url")),
        published_at=frontmatter.get("published_at"),
        duration_seconds=document.duration_seconds,
        license=frontmatter.get("license") or frontmatter.get("video_license"),
        meta=frontmatter.get("video_meta"),
    )

    chunk_hints = ensure_list(frontmatter.get("osis_refs"))
    if embedding_service is None:
        embedding_service = get_embedding_service()

    raw_texts: list[str] = []
    sanitized_texts: list[str] = []
    for chunk in chunks:
        raw_value = chunk.text
        sanitized_value = sanitize_passage_text(raw_value)
        raw_texts.append(raw_value)
        sanitized_texts.append(sanitized_value)

    embeddings = embedding_service.embed(sanitized_texts)

    passages: list[Passage] = []
    segments: list[TranscriptSegment] = []
    for idx, chunk in enumerate(chunks):
        sanitized_text = (
            sanitized_texts[idx]
            if idx < len(sanitized_texts)
            else sanitize_passage_text(chunk.text)
        )
        raw_text = raw_texts[idx] if idx < len(raw_texts) else chunk.text

        detected = detect_osis_references(sanitized_text)
        meta = normalise_passage_meta(
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
            text=sanitized_text,
            raw_text=raw_text,
            tokens=len(sanitized_text.split()),
            osis_ref=osis_value,
            embedding=embedding,
            lexeme=lexical_representation(session, sanitized_text),
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
            text=sanitized_text,
            raw_text=raw_text,
            primary_osis=osis_value,
            osis_refs=normalized_refs or None,
            topics=None,
            entities=None,
        )
        session.add(segment)
        segments.append(segment)

    session.flush()

    topics = collect_topics(document, frontmatter)
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
        confidence_default = (
            float(raw_confidence) if raw_confidence is not None else None
        )
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

    refresh_creator_verse_rollups(session, segments)

    storage_dir = settings.storage_root / document.id
    storage_dir.mkdir(parents=True, exist_ok=True)

    artifacts: dict[str, str] = {}

    if frontmatter:
        frontmatter_path = storage_dir / "frontmatter.json"
        frontmatter_path.write_text(
            serialise_frontmatter(frontmatter) + "\n", encoding="utf-8"
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


def persist_transcript_document(
    session: Session,
    *,
    chunks,
    parser: str,
    parser_version: str,
    frontmatter: dict[str, Any],
    settings,
    sha256: str,
    source_type: str,
    title: str | None,
    source_url: str | None,
    channel: str | None = None,
    video_id: str | None = None,
    duration_seconds: Any = None,
    transcript_path: Path | None = None,
    audio_path: Path | None = None,
    transcript_filename: str | None = None,
    audio_filename: str | None = None,
    embedding_service=None,
) -> Document:
    tradition, topic_domains = extract_guardrail_profile(frontmatter)

    ensure_unique_document_sha(session, sha256)

    normalised_source_url = normalise_source_url(
        source_url or frontmatter.get("source_url")
    )

    document = Document(
        id=str(uuid4()),
        title=title or frontmatter.get("title") or "Transcript",
        authors=ensure_list(frontmatter.get("authors")),
        doi=frontmatter.get("doi"),
        source_url=normalised_source_url,
        source_type=source_type,
        collection=frontmatter.get("collection"),
        pub_date=coerce_date(frontmatter.get("date")),
        year=coerce_int(frontmatter.get("year") or frontmatter.get("pub_year")),
        venue=frontmatter.get("venue"),
        abstract=frontmatter.get("abstract"),
        topics=normalise_topics_field(
            frontmatter.get("topics"),
            frontmatter.get("concepts"),
        ),
        channel=channel or frontmatter.get("channel"),
        video_id=video_id or frontmatter.get("video_id"),
        duration_seconds=coerce_int(duration_seconds)
        or coerce_int(frontmatter.get("duration_seconds"))
        or derive_duration_from_chunks(chunks),
        bib_json=frontmatter.get("bib_json"),
        theological_tradition=tradition,
        topic_domains=topic_domains,
        sha256=sha256,
    )

    try:
        session.add(document)
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise UnsupportedSourceError("Document already ingested") from exc

    creator_tags = ensure_list(frontmatter.get("creator_tags"))
    creator_profile = get_or_create_creator(
        session,
        name=frontmatter.get("creator"),
        channel=document.channel,
        bio=frontmatter.get("creator_bio"),
        tags=creator_tags,
    )

    video_record = get_or_create_video(
        session,
        creator=creator_profile,
        document=document,
        video_identifier=document.video_id,
        title=document.title,
        url=document.source_url or normalise_source_url(frontmatter.get("url")),
        published_at=frontmatter.get("published_at"),
        duration_seconds=document.duration_seconds,
        license=frontmatter.get("license") or frontmatter.get("video_license"),
        meta=frontmatter.get("video_meta"),
    )

    chunk_hints = ensure_list(frontmatter.get("osis_refs"))
    if embedding_service is None:
        embedding_service = get_embedding_service()
    embeddings = embedding_service.embed([chunk.text for chunk in chunks])

    passages: list[Passage] = []
    segments: list[TranscriptSegment] = []
    for idx, chunk in enumerate(chunks):
        detected = detect_osis_references(chunk.text)
        meta = normalise_passage_meta(
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

    topics = collect_topics(document, frontmatter)

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
                claim = CreatorClaim(
                    creator_id=creator_profile.id,
                    video_id=video_record.id if video_record else None,
                    segment_id=segment.id,
                    topic=topic,
                    stance="unknown",
                    claim_md=_truncate(segment.text, limit=600),
                    confidence=0.5,
                )
                session.add(claim)

    session.commit()

    refresh_creator_verse_rollups(session, segments)

    storage_dir = settings.storage_root / document.id
    storage_dir.mkdir(parents=True, exist_ok=True)

    artifacts: dict[str, str] = {}

    if frontmatter:
        frontmatter_path = storage_dir / "frontmatter.json"
        frontmatter_path.write_text(
            serialise_frontmatter(frontmatter) + "\n", encoding="utf-8"
        )
        artifacts.setdefault("frontmatter", frontmatter_path.name)

    if transcript_path and transcript_path.exists():
        dest_name = safe_storage_name(
            transcript_filename or transcript_path.name,
            fallback=transcript_path.name,
        )
        dest_path = storage_dir / dest_name
        shutil.copy(transcript_path, dest_path)
        artifacts["transcript"] = dest_path.name

    if audio_path and audio_path.exists():
        audio_name = safe_storage_name(
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


__all__ = [
    "ensure_unique_document_sha",
    "get_or_create_creator",
    "get_or_create_video",
    "persist_text_document",
    "persist_transcript_document",
    "refresh_creator_verse_rollups",
    "safe_storage_name",
]
