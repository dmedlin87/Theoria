"""Synchronization helpers for case builder domain objects."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
from typing import Iterable, Sequence

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..core.settings import get_settings
from ..db.models import (
    CaseObject,
    CaseSource,
    Document,
    DocumentAnnotation,
    Passage,
)
from ..ingest.embeddings import get_embedding_service

LOGGER = logging.getLogger(__name__)


def _normalise_list(value: object | None) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned or None
    if isinstance(value, dict):
        cleaned = [str(key).strip() for key in value.keys() if str(key).strip()]
        return cleaned or None
    text_value = str(value).strip()
    return [text_value] if text_value else None


def _coerce_float(value: object | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _ensure_case_source(
    session: Session, document: Document, frontmatter: dict[str, object] | None
) -> CaseSource:
    """Return a ``CaseSource`` row for *document*, creating it if required."""

    existing = session.execute(
        select(CaseSource).where(CaseSource.document_id == document.id)
    ).scalar_one_or_none()
    origin = str(frontmatter.get("collection")) if frontmatter and frontmatter.get("collection") else document.collection
    author = None
    if document.authors:
        author = next((author for author in document.authors if author), None)
    year = document.year
    modality = document.source_type or (frontmatter.get("modality") if frontmatter else None)
    meta: dict[str, object] | None = None
    if frontmatter:
        serialised: dict[str, object] = {}
        for key, value in frontmatter.items():
            if not isinstance(key, str):
                continue
            if value in (None, ""):
                continue
            if isinstance(value, (str, int, float, bool, list, dict)):
                serialised[key] = value
            else:
                serialised[key] = str(value)
        meta = serialised or None

    if existing is None:
        source = CaseSource(
            document_id=document.id,
            origin=origin,
            author=author,
            year=year,
            url=document.source_url,
            modality=modality,
            meta=meta,
        )
        session.add(source)
        session.flush()
        return source

    changed = False
    if origin and existing.origin != origin:
        existing.origin = origin
        changed = True
    if author and existing.author != author:
        existing.author = author
        changed = True
    if year and existing.year != year:
        existing.year = year
        changed = True
    if document.source_url and existing.url != document.source_url:
        existing.url = document.source_url
        changed = True
    if modality and existing.modality != modality:
        existing.modality = modality
        changed = True
    if meta and existing.meta != meta:
        existing.meta = meta
        changed = True
    if changed:
        existing.updated_at = datetime.now(UTC)
        session.add(existing)
    return existing


def _collect_osis_ranges(passage: Passage) -> list[str] | None:
    osis_values: list[str] = []
    if passage.osis_ref:
        osis_values.append(passage.osis_ref)
    meta = passage.meta or {}
    if isinstance(meta, dict):
        extra = meta.get("osis_refs_all")
        if isinstance(extra, list):
            for item in extra:
                text_item = str(item).strip()
                if text_item:
                    osis_values.append(text_item)
    unique = sorted({value for value in osis_values if value})
    return unique or None


def _update_case_object(
    session: Session,
    case_object: CaseObject | None,
    *,
    source: CaseSource | None,
    document: Document,
    body: str,
    object_type: str,
    osis_ranges: list[str] | None,
    modality: str | None,
    tags: list[str] | None,
    stability: float | None,
    embedding: Sequence[float] | None,
    meta: dict[str, object] | None,
    passage: Passage | None = None,
    annotation: DocumentAnnotation | None = None,
) -> tuple[CaseObject, bool]:
    now = datetime.now(UTC)
    if case_object is None:
        case_object = CaseObject(
            source_id=source.id if source else None,
            document_id=document.id,
            passage_id=passage.id if passage else None,
            annotation_id=annotation.id if annotation else None,
            object_type=object_type,
            title=document.title,
            body=body,
            osis_ranges=osis_ranges,
            modality=modality,
            tags=tags,
            stability=stability,
            embedding=list(embedding) if embedding is not None else None,
            published_at=document.pub_date,
            meta=meta,
        )
        session.add(case_object)
        return case_object, True

    changed = False
    if source and case_object.source_id != source.id:
        case_object.source_id = source.id
        changed = True
    if case_object.document_id != document.id:
        case_object.document_id = document.id
        changed = True
    if passage and case_object.passage_id != passage.id:
        case_object.passage_id = passage.id
        changed = True
    if annotation and case_object.annotation_id != annotation.id:
        case_object.annotation_id = annotation.id
        changed = True
    if case_object.object_type != object_type:
        case_object.object_type = object_type
        changed = True
    if case_object.title != document.title:
        case_object.title = document.title
        changed = True
    if case_object.body != body:
        case_object.body = body
        changed = True
    if case_object.osis_ranges != osis_ranges:
        case_object.osis_ranges = osis_ranges
        changed = True
    if case_object.modality != modality:
        case_object.modality = modality
        changed = True
    if case_object.tags != tags:
        case_object.tags = tags
        changed = True
    if case_object.stability != stability:
        case_object.stability = stability
        changed = True
    if embedding is not None and case_object.embedding != list(embedding):
        case_object.embedding = list(embedding)
        changed = True
    if case_object.published_at != document.pub_date:
        case_object.published_at = document.pub_date
        changed = True
    if case_object.meta != meta:
        case_object.meta = meta
        changed = True
    if changed:
        case_object.updated_at = now
        session.add(case_object)
    return case_object, changed


def emit_case_object_notifications(session: Session, case_object_ids: Iterable[str]) -> None:
    """Emit Postgres notifications for the provided case object identifiers."""

    ids = [identifier for identifier in case_object_ids if identifier]
    if not ids:
        return

    bind = session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return

    settings = get_settings()
    channel = settings.case_builder_notify_channel
    for identifier in ids:
        payload = json.dumps({"case_object_id": identifier})
        session.execute(
            text("SELECT pg_notify(:channel, :payload)"),
            {"channel": channel, "payload": payload},
        )


def sync_passages_case_objects(
    session: Session,
    *,
    document: Document,
    passages: Sequence[Passage],
    frontmatter: dict[str, object] | None = None,
) -> list[str]:
    """Ensure each passage surfaces as a ``CaseObject`` row."""

    settings = get_settings()
    if not settings.case_builder_enabled:
        return []

    source = _ensure_case_source(session, document, frontmatter)
    tags = _normalise_list(document.topics)
    stability = _coerce_float((frontmatter or {}).get("stability"))
    changed_ids: list[str] = []

    for passage in passages:
        osis_ranges = _collect_osis_ranges(passage)
        meta_payload: dict[str, object] = {
            "passage_meta": passage.meta or {},
            "passage_id": passage.id,
        }
        meta = {k: v for k, v in meta_payload.items() if v is not None}
        case_object = session.execute(
            select(CaseObject).where(CaseObject.passage_id == passage.id)
        ).scalar_one_or_none()
        case_object, changed = _update_case_object(
            session,
            case_object,
            source=source,
            document=document,
            passage=passage,
            annotation=None,
            body=passage.text,
            object_type="passage",
            osis_ranges=osis_ranges,
            modality=document.source_type,
            tags=tags,
            stability=stability,
            embedding=passage.embedding,
            meta=meta,
        )
        if changed:
            changed_ids.append(case_object.id)

    if changed_ids:
        emit_case_object_notifications(session, changed_ids)
    return changed_ids


def sync_annotation_case_object(
    session: Session,
    *,
    document: Document,
    annotation: DocumentAnnotation,
) -> str | None:
    """Persist a ``CaseObject`` representing *annotation* when enabled."""

    settings = get_settings()
    if not settings.case_builder_enabled:
        return None

    source = _ensure_case_source(session, document, None)
    case_object = session.execute(
        select(CaseObject).where(CaseObject.annotation_id == annotation.id)
    ).scalar_one_or_none()

    body = annotation.body.strip()
    if not body:
        LOGGER.debug("Skipping empty annotation %s for case builder", annotation.id)
        return None

    embedding: list[float] | None = None
    try:
        embedding_service = get_embedding_service()
        embedding_vectors = embedding_service.embed([body])
        embedding = list(embedding_vectors[0]) if embedding_vectors else None
    except Exception:  # pragma: no cover - defensive fallback
        LOGGER.exception("Failed to embed annotation %s for case builder", annotation.id)
        embedding = None

    tags = _normalise_list(document.topics)
    case_object, changed = _update_case_object(
        session,
        case_object,
        source=source,
        document=document,
        passage=None,
        annotation=annotation,
        body=body,
        object_type="annotation",
        osis_ranges=None,
        modality=document.source_type,
        tags=tags,
        stability=None,
        embedding=embedding,
        meta={"annotation_created_at": annotation.created_at.isoformat()},
    )

    if changed:
        emit_case_object_notifications(session, [case_object.id])
    return case_object.id
