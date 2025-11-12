"""Facade exposing document persistence helpers to the application layer."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from theo.adapters import AdapterRegistry
from theo.adapters.persistence.models import Document as DocumentRecord, Passage
from theo.domain import Document, DocumentId, DocumentMetadata

__all__ = [
    "DocumentCommands",
    "build_document_facade",
]


class DocumentCommands(Protocol):
    """Protocol describing document lifecycle operations."""

    def ingest(self, document: Document) -> DocumentId: ...

    def retire(self, document_id: DocumentId) -> None: ...

    def get(self, document_id: DocumentId) -> Document | None: ...

    def list(self, *, limit: int = 20) -> list[Document]: ...


@contextmanager
def _session_scope(registry: AdapterRegistry) -> Iterator[Session]:
    engine = registry.resolve("engine")
    with Session(engine) as session:
        yield session


def _extract_language(record: DocumentRecord) -> str | None:
    payload = record.bib_json if isinstance(record.bib_json, dict) else {}
    language = payload.get("language") or payload.get("lang")
    return str(language) if isinstance(language, str) and language.strip() else None


def _extract_tags(record: DocumentRecord) -> list[str]:
    tags: list[str] = []
    if isinstance(record.topics, list):
        tags.extend(str(item) for item in record.topics if isinstance(item, str) and item)
    elif isinstance(record.topics, dict):
        tags.extend(
            str(value)
            for value in record.topics.values()
            if isinstance(value, str) and value
        )

    payload = record.bib_json if isinstance(record.bib_json, dict) else {}
    extra_tags = payload.get("tags")
    if isinstance(extra_tags, (list, tuple, set)):
        tags.extend(str(item) for item in extra_tags if isinstance(item, str) and item)

    seen: set[str] = set()
    unique: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            unique.append(tag)
    return unique


def _extract_scripture_refs(session: Session, record: DocumentRecord) -> tuple[str, ...]:
    refs: list[str] = []
    seen: set[str] = set()

    payload = record.bib_json if isinstance(record.bib_json, dict) else {}
    stored_refs = payload.get("scripture_refs") or payload.get("scriptureRefs")
    if isinstance(stored_refs, (list, tuple, set)):
        for value in stored_refs:
            if isinstance(value, str) and value and value not in seen:
                seen.add(value)
                refs.append(value)

    passage_stmt = (
        select(Passage.osis_ref)
        .where(Passage.document_id == record.id, Passage.osis_ref.is_not(None))
        .order_by(Passage.page_no.asc(), Passage.t_start.asc(), Passage.start_char.asc())
    )
    for row in session.execute(passage_stmt):
        osis_ref = row[0]
        if isinstance(osis_ref, str) and osis_ref and osis_ref not in seen:
            seen.add(osis_ref)
            refs.append(osis_ref)

    return tuple(refs)


def _document_from_record(session: Session, record: DocumentRecord) -> Document:
    title = record.title or record.id
    source = (
        record.collection
        or record.source_type
        or record.source_url
        or "unknown"
    )
    metadata = DocumentMetadata(
        title=title,
        source=source,
        language=_extract_language(record),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )

    scripture_refs = _extract_scripture_refs(session, record)
    tags = tuple(_extract_tags(record))

    return Document(
        id=DocumentId(record.id),
        metadata=metadata,
        scripture_refs=scripture_refs,
        tags=tags,
        checksum=record.sha256,
    )


def build_document_facade(registry: AdapterRegistry) -> DocumentCommands:
    """Return callables performing document lifecycle operations."""

    class _Facade:
        def ingest(self, document: Document) -> DocumentId:
            with _session_scope(registry) as session:
                record = session.get(DocumentRecord, str(document.id))
                if record is None:
                    record = DocumentRecord(id=str(document.id))

                record.title = document.metadata.title
                if document.metadata.source:
                    record.collection = document.metadata.source
                record.source_type = record.source_type or "graphql"
                if document.metadata.created_at is not None:
                    record.created_at = document.metadata.created_at
                if document.metadata.updated_at is not None:
                    record.updated_at = document.metadata.updated_at
                if document.checksum:
                    record.sha256 = document.checksum

                existing_payload = record.bib_json if isinstance(record.bib_json, dict) else {}
                payload = dict(existing_payload)
                if document.metadata.language:
                    payload.setdefault("language", document.metadata.language)
                if document.scripture_refs:
                    payload["scripture_refs"] = list(document.scripture_refs)
                if document.tags:
                    payload_tags = list(payload.get("tags") or [])
                    payload_tags.extend(document.tags)
                    deduped_tags: list[str] = []
                    seen_tags: set[str] = set()
                    for tag in payload_tags:
                        if isinstance(tag, str) and tag and tag not in seen_tags:
                            seen_tags.add(tag)
                            deduped_tags.append(tag)
                    payload["tags"] = deduped_tags
                    record.topics = deduped_tags or None
                record.bib_json = payload or None

                session.add(record)
                session.commit()

            return document.id

        def retire(self, document_id: DocumentId) -> None:
            with _session_scope(registry) as session:
                record = session.get(DocumentRecord, str(document_id))
                if record is None:
                    return
                session.delete(record)
                session.commit()

        def get(self, document_id: DocumentId) -> Document | None:
            with _session_scope(registry) as session:
                record = session.get(DocumentRecord, str(document_id))
                if record is None:
                    return None
                return _document_from_record(session, record)

        def list(self, *, limit: int = 20) -> list[Document]:
            normalised_limit = max(1, int(limit)) if isinstance(limit, int) else 20

            with _session_scope(registry) as session:
                stmt = (
                    select(DocumentRecord)
                    .order_by(DocumentRecord.created_at.desc())
                    .limit(normalised_limit)
                )
                records = session.scalars(stmt).all()
                return [_document_from_record(session, record) for record in records]

    return _Facade()
