"""Utilities for mirroring ingested artifacts into the Case Builder store."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, Sequence

from sqlalchemy.orm import Session

from theo.application.facades.settings import Settings, get_settings
from theo.platform.events import event_bus
from theo.platform.events.types import CaseObjectsUpsertedEvent
from theo.services.api.app.persistence_models import (
    CaseObject,
    CaseObjectType,
    CaseSource,
    Document,
    Passage,
)


def _feature_enabled(settings: Settings | None = None) -> bool:
    """Return ``True`` when Case Builder ingestion should run."""

    settings = settings or get_settings()
    return bool(getattr(settings, "case_builder_enabled", False))


def _extract_osis_ranges(passage: Passage) -> list[str]:
    osis_refs: list[str] = []
    if passage.osis_ref:
        osis_refs.append(passage.osis_ref)
    meta = getattr(passage, "meta", None)
    if isinstance(meta, dict):
        raw_refs = meta.get("osis_refs_all")
        if isinstance(raw_refs, (list, tuple)):
            osis_refs.extend(str(item) for item in raw_refs if item)
    return sorted({ref for ref in osis_refs if ref})


def _extract_stability(passage: Passage) -> float | None:
    meta = getattr(passage, "meta", None)
    if isinstance(meta, dict):
        stability = meta.get("stability")
        if stability is None:
            stability = meta.get("stability_score")
        if stability is not None:
            try:
                return float(stability)
            except (TypeError, ValueError):
                return None
    return None


def _build_passage_metadata(passage: Passage) -> dict[str, object] | None:
    meta = getattr(passage, "meta", None)
    if isinstance(meta, dict):
        # ``meta`` may be a custom mapping type – coerce to plain ``dict``.
        try:
            return dict(meta)
        except TypeError:
            return {key: meta[key] for key in meta.keys()}
    return None


def _source_meta(document: Document) -> dict[str, Any] | None:
    payload: dict[str, object] = {}
    if document.authors:
        payload["authors"] = list(document.authors)
    if document.collection:
        payload["collection"] = document.collection
    if document.topics:
        payload["topics"] = document.topics
    if document.topic_domains:
        payload["topic_domains"] = document.topic_domains
    if document.channel:
        payload["channel"] = document.channel
    if document.video_id:
        payload["video_id"] = document.video_id
    if document.duration_seconds is not None:
        payload["duration_seconds"] = document.duration_seconds
    if not payload:
        return None
    return payload


def _get_or_create_source(session: Session, document: Document) -> CaseSource | None:
    existing = (
        session.query(CaseSource)
        .filter(CaseSource.document_id == document.id)
        .one_or_none()
    )
    if existing is not None:
        updated = False
        author = None
        if document.authors:
            author = document.authors[0]
        if author and existing.author != author:
            existing.author = author
            updated = True
        if document.year and existing.year != document.year:
            existing.year = document.year
            updated = True
        if document.source_url and existing.url != document.source_url:
            existing.url = document.source_url
            updated = True
        if document.source_type and existing.modality != document.source_type:
            existing.modality = document.source_type
            updated = True
        meta = _source_meta(document)
        if meta != existing.meta:
            existing.meta = meta
            updated = True
        if updated:
            existing.updated_at = datetime.now(UTC)
        return existing

    author = None
    if document.authors:
        author = document.authors[0]
    source = CaseSource(
        document_id=document.id,
        origin=document.collection,
        author=author,
        year=document.year,
        url=document.source_url,
        modality=document.source_type,
        meta=_source_meta(document),
    )
    session.add(source)
    session.flush()
    return source


def _notify_new_objects(
    session: Session,
    object_ids: Sequence[str],
    settings: Settings,
    *,
    document_id: str | None = None,
) -> None:
    if not object_ids:
        return
    event_bus.publish(
        CaseObjectsUpsertedEvent.from_ids(object_ids, document_id=document_id)
    )


try:
    from inspect import signature as _inspect_signature
except ImportError:  # pragma: no cover - standard library availability
    _inspect_signature = None


@lru_cache(maxsize=16)
def _notify_supports_document_id(callback: object) -> bool:
    if _inspect_signature is None:
        return False
    try:
        parameters = _inspect_signature(callback).parameters
    except (TypeError, ValueError):
        return False
    return "document_id" in parameters


def sync_case_objects_for_document(
    session: Session,
    *,
    document: Document,
    passages: Sequence[Passage],
    settings: Settings | None = None,
) -> list[CaseObject]:
    """Ensure Case Builder records exist for *document* and its *passages*."""

    settings = settings or get_settings()
    if not _feature_enabled(settings):
        return []

    if not passages:
        return []

    source = _get_or_create_source(session, document)

    topic_tags: list[str] = []
    if document.topic_domains:
        topic_tags.extend(str(tag) for tag in document.topic_domains if tag)
    if document.topics:
        topic_tags.extend(str(tag) for tag in document.topics if tag)

    created_objects: list[CaseObject] = []
    updated_objects: list[CaseObject] = []
    passage_ids = [passage.id for passage in passages if passage.id is not None]
    existing_by_passage_id: dict[str, CaseObject] = {}
    if passage_ids:
        existing_objects = (
            session.query(CaseObject)
            .filter(CaseObject.passage_id.in_(passage_ids))
            .all()
        )
        existing_by_passage_id = {obj.passage_id: obj for obj in existing_objects}

    for passage in passages:
        existing = existing_by_passage_id.get(passage.id)

        osis_ranges = _extract_osis_ranges(passage)
        meta = _build_passage_metadata(passage)
        stability = _extract_stability(passage)

        if existing is None:
            case_object = CaseObject(
                source_id=source.id if source else None,
                document_id=document.id,
                passage_id=passage.id,
                object_type=CaseObjectType.PASSAGE,
                title=document.title,
                body=passage.text,
                osis_ranges=osis_ranges or None,
                modality=document.source_type,
                tags=topic_tags or None,
                embedding=passage.embedding,
                stability=stability,
                meta=meta,
                published_at=document.pub_date,
            )
            session.add(case_object)
            if passage.id is not None:
                existing_by_passage_id[passage.id] = case_object
            created_objects.append(case_object)
        else:
            updated = False

            new_source_id = source.id if source else existing.source_id
            if existing.source_id != new_source_id:
                existing.source_id = new_source_id
                updated = True

            if existing.title != document.title:
                existing.title = document.title
                updated = True

            if existing.body != passage.text:
                existing.body = passage.text
                updated = True

            new_osis_ranges = osis_ranges or None
            if existing.osis_ranges != new_osis_ranges:
                existing.osis_ranges = new_osis_ranges
                updated = True

            if existing.modality != document.source_type:
                existing.modality = document.source_type
                updated = True

            new_tags = topic_tags or None
            if existing.tags != new_tags:
                existing.tags = new_tags
                updated = True

            if existing.embedding != passage.embedding:
                existing.embedding = passage.embedding
                updated = True

            if existing.stability != stability:
                existing.stability = stability
                updated = True

            if existing.meta != meta:
                existing.meta = meta
                updated = True

            if existing.published_at != document.pub_date:
                existing.published_at = document.pub_date
                updated = True

            if updated:
                existing.updated_at = datetime.now(UTC)
                updated_objects.append(existing)
            session.add(existing)

    session.flush()
    notified_ids: list[str] = []
    if created_objects:
        notified_ids.extend(obj.id for obj in created_objects)
    if updated_objects:
        notified_ids.extend(obj.id for obj in updated_objects)
    if notified_ids:
        notify_kwargs: dict[str, object] = {}
        notify_callable = _notify_new_objects
        if _notify_supports_document_id(notify_callable):
            notify_kwargs["document_id"] = document.id
        notify_callable(
            session,
            notified_ids,
            settings,
            **notify_kwargs,
        )
    return created_objects


__all__ = ["sync_case_objects_for_document"]
