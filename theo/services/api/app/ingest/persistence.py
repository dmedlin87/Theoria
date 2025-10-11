"""Database persistence helpers for ingestion."""

from __future__ import annotations

import json
import shutil
import tempfile
import logging
from pathlib import Path
from typing import Any, Sequence
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..case_builder import sync_passages_case_objects
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
from .embeddings import lexical_representation
from .exceptions import UnsupportedSourceError
from .metadata import (
    build_source_ref,
    coerce_date,
    coerce_datetime,
    coerce_int,
    collect_topics,
    derive_duration_from_chunks,
    ensure_list,
    extract_guardrail_profile,
    normalise_passage_meta,
    normalise_source_url,
    normalise_topics_field,
    sanitise_chunks,
    serialise_frontmatter,
    truncate,
)
from .osis import detect_osis_references, expand_osis_reference
from .sanitizer import sanitize_passage_text


logger = logging.getLogger(__name__)


from .stages import IngestContext


def _collect_osis_verse_ids(references: Sequence[str]) -> list[int]:
    """Return sorted verse identifiers for the supplied OSIS references."""

    verse_ids: set[int] = set()
    for reference in references:
        if not reference:
            continue
        try:
            verse_ids.update(expand_osis_reference(reference))
        except Exception:  # pragma: no cover - defensive in case of malformed refs
            continue
    return sorted(verse_ids)


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


def _collect_verse_ids(references: Sequence[str] | None) -> list[int] | None:
    """Return sorted verse identifiers for *references* or ``None`` when empty."""

    if not references:
        return None

    verse_ids: set[int] = set()
    for reference in references:
        if reference:
            verse_ids.update(expand_osis_reference(reference))

    if not verse_ids:
        return None

    return sorted(verse_ids)


def refresh_creator_verse_rollups(
    session: Session,
    segments: list[TranscriptSegment],
    *,
    context: IngestContext,
) -> None:
    """Refresh cached creator verse rollups impacted by *segments*."""

    osis_refs: set[str] = set()
    for segment in segments:
        if segment.osis_refs:
            osis_refs.update(segment.osis_refs)

    if not osis_refs:
        return

    settings = context.settings
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
        except Exception:  # pragma: no cover - async fallbacks
            pass

    service = CreatorVersePerspectiveService(session)
    service.refresh_many(sorted_refs)


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


def _calculate_snapshot_size(
    text_content: str | None, chunks: Sequence[Any]
) -> int:
    """Estimate the number of bytes required for normalized text snapshots."""

    total = 0
    if text_content:
        total += len(text_content.encode("utf-8"))

    for chunk in chunks:
        chunk_text = getattr(chunk, "text", "") or ""
        if chunk_text:
            total += len(chunk_text.encode("utf-8"))

    return total


def _should_embed_snapshot(
    *, text_content: str | None, chunks: Sequence[Any], settings: Any
) -> bool:
    """Return ``True`` when normalized snapshots should inline text data."""

    threshold = getattr(settings, "ingest_normalized_snapshot_max_bytes", None)
    if threshold in (None, 0):
        return True

    try:
        limit = int(threshold)
    except (TypeError, ValueError):
        return True

    if limit <= 0:
        return True

    return _calculate_snapshot_size(text_content, chunks) <= limit


def _build_snapshot_manifest(
    *,
    document_id: str,
    artifacts: dict[str, str],
    storage_dir: Path,
    settings: Any,
) -> dict[str, Any] | None:
    """Construct a manifest that references stored artifacts for large ingests."""

    if not artifacts:
        return None

    base_url = getattr(settings, "storage_public_base_url", None)
    manifest_entries: dict[str, dict[str, str]] = {}

    for label, filename in artifacts.items():
        entry: dict[str, str] = {
            "filename": filename,
            "relative_path": filename,
        }
        if base_url:
            entry["uri"] = "/".join(
                segment.strip("/")
                for segment in (base_url, document_id, filename)
                if segment
            )
        else:
            entry["uri"] = str(storage_dir / filename)
        manifest_entries[label] = entry

    return {"artifacts": manifest_entries}


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


def persist_text_document(
    session: Session,
    *,
    context: IngestContext,
    chunks,
    parser: str,
    parser_version: str,
    frontmatter: dict[str, Any],
    sha256: str,
    source_type: str,
    title: str | None,
    source_url: str | None,
    text_content: str,
    original_path: Path | None = None,
    raw_content: str | None = None,
    raw_filename: str | None = None,
) -> Document:
    from .chunking import Chunk

    if not isinstance(chunks, list) or not all(isinstance(c, Chunk) for c in chunks):
        raise ValueError("chunks must be a list of Chunk instances")

    settings = context.settings

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

    raw_texts, sanitized_texts = sanitise_chunks(chunks)
    embeddings = context.embedding_service.embed(sanitized_texts)
    sanitized_document_text = "\n\n".join(
        text for text in sanitized_texts if text
    ) or sanitize_passage_text(text_content)

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
        osis_all: list[str] = []
        if meta.get("osis_refs_all"):
            osis_all.extend(meta["osis_refs_all"])
        if osis_value:
            osis_all.append(osis_value)
        normalized_refs = sorted({ref for ref in osis_all if ref})
        verse_ids = _collect_verse_ids(normalized_refs)

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
            osis_verse_ids=verse_ids,
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

        verse_ids = _collect_osis_verse_ids(normalized_refs)

        segment = TranscriptSegment(
            document_id=document.id,
            video_id=video_record.id if video_record else None,
            t_start=chunk.t_start,
            t_end=chunk.t_end,
            text=sanitized_text,
            primary_osis=osis_value,
            osis_refs=normalized_refs or None,
            osis_verse_ids=verse_ids or None,
            topics=None,
            entities=None,
        )
        session.add(segment)
        segments.append(segment)

    session.flush()

    if getattr(settings, "case_builder_enabled", False):
        try:
            from ..case_builder import ingest as case_builder_ingest

            case_builder_ingest.sync_case_objects_for_document(
                session,
                document=document,
                passages=passages,
                settings=settings,
            )
        except Exception:  # pragma: no cover - defensive logging
            logger.exception(
                "Case Builder sync failed during text ingestion",
                extra={"document_id": document.id},
            )
    sync_passages_case_objects(
        session,
        document=document,
        passages=passages,
        frontmatter=frontmatter,
    )

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
                quote_md=truncate(segment.text),
                osis_refs=segment.osis_refs,
                source_ref=build_source_ref(
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
                    claim_md=truncate(segment.text, limit=600),
                    confidence=(
                        confidence_default if confidence_default is not None else 0.5
                    ),
                )
                session.add(claim)

    storage_root = settings.storage_root
    storage_dir = storage_root / document.id
    temp_dir_path: Path | None = None
    moved_to_final = False

    try:
        storage_root.mkdir(parents=True, exist_ok=True)
        temp_dir_path = Path(
            tempfile.mkdtemp(prefix=f".{document.id}-", dir=storage_root)
        )

        artifacts: dict[str, str] = {}

        if original_path:
            safe_name = _safe_storage_name(
                original_path.name, fallback=original_path.name
            )
            destination = temp_dir_path / safe_name
            if original_path != destination:
                shutil.copyfile(original_path, destination)
            artifacts.setdefault("original", safe_name)

        if raw_content:
            filename = raw_filename or "raw.txt"
            safe_name = _safe_storage_name(filename, fallback=filename)
            target_path = temp_dir_path / safe_name
            target_path.write_text(raw_content, encoding="utf-8")
            artifacts.setdefault("raw", safe_name)

        embed_snapshot = _should_embed_snapshot(
            text_content=sanitized_document_text,
            chunks=chunks,
            settings=settings,
        )
        snapshot_manifest: dict[str, Any] | None = None

        normalized_payload = {
            "document": {
                "id": document.id,
                "title": document.title,
                "source_url": document.source_url,
                "source_type": document.source_type,
            },
            "passages": [
                {
                    "id": passage.id,
                    "osis_ref": passage.osis_ref,
                    "tokens": passage.tokens,
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

        if sanitized_document_text:
            content_filename = "content.txt"
            content_path = temp_dir_path / content_filename
            content_path.write_text(sanitized_document_text, encoding="utf-8")
            artifacts.setdefault("content", content_filename)

        if embed_snapshot:
            normalized_payload["document"]["text"] = sanitized_document_text
            normalized_payload["chunks"] = [
                {
                    "index": chunk.index,
                    "text": sanitized_texts[idx]
                    if idx < len(sanitized_texts)
                    else sanitize_passage_text(chunk.text),
                    "t_start": chunk.t_start,
                    "t_end": chunk.t_end,
                    "page_no": chunk.page_no,
                }
                for idx, chunk in enumerate(chunks)
            ]
        else:
            snapshot_manifest = _build_snapshot_manifest(
                document_id=document.id,
                artifacts=artifacts,
                storage_dir=storage_dir,
                settings=settings,
            )

        if artifacts:
            normalized_payload["artifacts"] = artifacts

        _write_document_metadata(
            temp_dir_path,
            frontmatter=frontmatter,
            normalized_payload=normalized_payload,
            snapshot_manifest=snapshot_manifest,
        )

        if storage_dir.exists():
            shutil.rmtree(storage_dir)
        shutil.move(str(temp_dir_path), storage_dir)
        moved_to_final = True

        document.storage_path = str(storage_dir)
        session.add(document)
        session.commit()
    except Exception:
        session.rollback()
        if moved_to_final:
            shutil.rmtree(storage_dir, ignore_errors=True)
        elif temp_dir_path is not None:
            shutil.rmtree(temp_dir_path, ignore_errors=True)
        raise

    return document


def _write_document_metadata(
    target_dir: Path,
    *,
    frontmatter: dict[str, Any],
    normalized_payload: dict[str, Any],
    snapshot_manifest: dict[str, Any] | None = None,
) -> None:
    """Write frontmatter and normalized payload metadata files."""

    target_dir.joinpath("frontmatter.json").write_text(
        serialise_frontmatter(frontmatter), encoding="utf-8"
    )

    payload = dict(normalized_payload)
    if snapshot_manifest:
        payload["snapshot_manifest"] = snapshot_manifest

    target_dir.joinpath("normalized.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def persist_transcript_document(
    session: Session,
    *,
    context: IngestContext,
    chunks,
    parser: str,
    parser_version: str,
    frontmatter: dict[str, Any],
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
    from .chunking import Chunk
    if not isinstance(chunks, list) or not all(isinstance(c, Chunk) for c in chunks):
        raise ValueError("chunks must be a list of Chunk instances")

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
    raw_texts, sanitized_texts = sanitise_chunks(chunks)
    settings = context.settings
    embeddings = context.embedding_service.embed(sanitized_texts)
    sanitized_document_text = "\n\n".join(
        text for text in sanitized_texts if text
    )

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
        osis_all: list[str] = []
        if meta.get("osis_refs_all"):
            osis_all.extend(meta["osis_refs_all"])
        if osis_value:
            osis_all.append(osis_value)
        normalized_refs = sorted({ref for ref in osis_all if ref})
        verse_ids = _collect_verse_ids(normalized_refs)

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
            osis_verse_ids=verse_ids,
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

        verse_ids = _collect_osis_verse_ids(normalized_refs)

        segment = TranscriptSegment(
            document_id=document.id,
            video_id=video_record.id if video_record else None,
            t_start=chunk.t_start,
            t_end=chunk.t_end,
            text=sanitized_text,
            primary_osis=osis_value,
            osis_refs=normalized_refs or None,
            osis_verse_ids=verse_ids or None,
            topics=None,
            entities=None,
        )
        session.add(segment)
        segments.append(segment)

    session.flush()

    if getattr(settings, "case_builder_enabled", False):
        try:
            from ..case_builder import ingest as case_builder_ingest

            case_builder_ingest.sync_case_objects_for_document(
                session,
                document=document,
                passages=passages,
                settings=settings,
            )
        except Exception:  # pragma: no cover - defensive logging
            logger.exception(
                "Case Builder sync failed during transcript ingestion",
                extra={"document_id": document.id},
            )
    sync_passages_case_objects(
        session,
        document=document,
        passages=passages,
        frontmatter=frontmatter,
    )

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
                quote_md=truncate(segment.text),
                osis_refs=segment.osis_refs,
                source_ref=build_source_ref(
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
                    claim_md=truncate(segment.text, limit=600),
                    confidence=(
                        confidence_default if confidence_default is not None else 0.5
                    ),
                )
                session.add(claim)

    storage_root = settings.storage_root
    storage_dir = storage_root / document.id
    temp_dir_path: Path | None = None
    moved_to_final = False

    try:
        storage_root.mkdir(parents=True, exist_ok=True)
        temp_dir_path = Path(
            tempfile.mkdtemp(prefix=f".{document.id}-", dir=storage_root)
        )
        artifacts: dict[str, str] = {}

        if transcript_path:
            safe_name = _safe_storage_name(
                transcript_filename or transcript_path.name,
                fallback=transcript_path.name,
            )
            destination = temp_dir_path / safe_name
            if transcript_path != destination:
                shutil.copyfile(transcript_path, destination)
            artifacts.setdefault("transcript", safe_name)

        if audio_path:
            filename = audio_filename or audio_path.name
            safe_name = _safe_storage_name(filename, fallback=audio_path.name)
            destination = temp_dir_path / safe_name
            if audio_path != destination:
                shutil.copyfile(audio_path, destination)
            artifacts.setdefault("audio", safe_name)

        embed_snapshot = _should_embed_snapshot(
            text_content=sanitized_document_text,
            chunks=chunks,
            settings=settings,
        )
        snapshot_manifest: dict[str, Any] | None = None

        normalized_payload = {
            "document": {
                "id": document.id,
                "title": document.title,
                "source_url": document.source_url,
                "source_type": document.source_type,
            },
            "passages": [
                {
                    "id": passage.id,
                    "osis_ref": passage.osis_ref,
                    "tokens": passage.tokens,
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

        if sanitized_document_text:
            content_filename = "content.txt"
            content_path = temp_dir_path / content_filename
            content_path.write_text(sanitized_document_text, encoding="utf-8")
            artifacts.setdefault("content", content_filename)

        if embed_snapshot:
            normalized_payload["document"]["text"] = sanitized_document_text
            normalized_payload["chunks"] = [
                {
                    "index": chunk.index,
                    "text": sanitized_texts[idx]
                    if idx < len(sanitized_texts)
                    else sanitize_passage_text(chunk.text),
                    "t_start": chunk.t_start,
                    "t_end": chunk.t_end,
                    "page_no": chunk.page_no,
                }
                for idx, chunk in enumerate(chunks)
            ]
        else:
            snapshot_manifest = _build_snapshot_manifest(
                document_id=document.id,
                artifacts=artifacts,
                storage_dir=storage_dir,
                settings=settings,
            )

        if artifacts:
            normalized_payload["artifacts"] = artifacts

        _write_document_metadata(
            temp_dir_path,
            frontmatter=frontmatter,
            normalized_payload=normalized_payload,
            snapshot_manifest=snapshot_manifest,
        )

        if storage_dir.exists():
            shutil.rmtree(storage_dir)
        shutil.move(str(temp_dir_path), storage_dir)
        moved_to_final = True

        document.storage_path = str(storage_dir)
        session.add(document)
        session.commit()
    except Exception:
        session.rollback()
        if moved_to_final:
            shutil.rmtree(storage_dir, ignore_errors=True)
        elif temp_dir_path is not None:
            shutil.rmtree(temp_dir_path, ignore_errors=True)
        raise

    refresh_creator_verse_rollups(session, segments, context=context)

    return document


def _safe_storage_name(name: str, *, fallback: str) -> str:
    """Return a safe filename for persisted artifacts."""

    candidate = name.replace("\\", "/")
    candidate = Path(candidate).name
    if candidate in {"", ".", ".."}:
        candidate = Path(fallback.replace("\\", "/")).name

    if candidate in {"", ".", ".."}:
        raise ValueError("artifact filename resolves outside storage directory")

    return candidate

