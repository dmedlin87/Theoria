"""Application bootstrap helpers wiring the service container."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from theo.adapters import AdapterRegistry
from theo.adapters.persistence.embedding_repository import (
    SQLAlchemyPassageEmbeddingRepository,
)
from theo.adapters.persistence.models import Document as DocumentRecord, Passage
from theo.adapters.research import (
    SqlAlchemyHypothesisRepositoryFactory,
    SqlAlchemyResearchNoteRepositoryFactory,
)
from theo.application.embeddings import EmbeddingRebuildService
from theo.application.facades.database import get_engine
from theo.application.facades.settings import get_settings
from theo.application.reasoner import NeighborhoodReasoner
from theo.application.research import ResearchService
from theo.domain import Document, DocumentId, DocumentMetadata

from .container import ApplicationContainer


@contextmanager
def _session_scope(registry: AdapterRegistry) -> Iterator[Session]:
    """Yield a SQLAlchemy session bound to the registry's engine."""

    engine = registry.resolve("engine")
    with Session(engine) as session:
        yield session


def _extract_language(record: DocumentRecord) -> str | None:
    """Derive the document's language from stored metadata."""

    payload = record.bib_json if isinstance(record.bib_json, dict) else {}
    language = payload.get("language") or payload.get("lang")
    return str(language) if isinstance(language, str) and language.strip() else None


def _extract_tags(record: DocumentRecord) -> list[str]:
    """Collect tag metadata from the document record."""

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
    """Return ordered scripture references associated with a document."""

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
    """Convert a persistence model into the domain aggregate."""

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


def _list_documents(registry: AdapterRegistry, *, limit: int = 20) -> list[Document]:
    """Return a list of documents ordered by recency."""

    normalised_limit = max(1, int(limit)) if isinstance(limit, int) else 20

    with _session_scope(registry) as session:
        stmt = (
            select(DocumentRecord)
            .order_by(DocumentRecord.created_at.desc())
            .limit(normalised_limit)
        )
        records = session.scalars(stmt).all()
        return [_document_from_record(session, record) for record in records]


def _get_document(registry: AdapterRegistry, document_id: DocumentId) -> Document | None:
    """Fetch a single document by identifier."""

    with _session_scope(registry) as session:
        record = session.get(DocumentRecord, str(document_id))
        if record is None:
            return None
        return _document_from_record(session, record)


def _ingest_document(registry: AdapterRegistry, document: Document) -> DocumentId:
    """Persist minimal document metadata originating from GraphQL."""

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


def _retire_document(registry: AdapterRegistry, document_id: DocumentId) -> None:
    """Remove a document and its dependent records."""

    with _session_scope(registry) as session:
        record = session.get(DocumentRecord, str(document_id))
        if record is None:
            return
        session.delete(record)
        session.commit()


def bootstrap_application(
    *,
    registry: AdapterRegistry,
    command_factory: Callable[[], Callable[[Document], DocumentId]],
    retire_factory: Callable[[], Callable[[DocumentId], None]],
    get_factory: Callable[[], Callable[[DocumentId], Document | None]],
    list_factory: Callable[[], Callable[..., list[Document]]],
    research_factory: Callable[[], Callable[[Session], ResearchService]],
) -> ApplicationContainer:
    """Construct an :class:`ApplicationContainer` wired to registered adapters."""

    ingest = command_factory()
    retire = retire_factory()
    get = get_factory()
    list_docs = list_factory()
    research = research_factory

    return ApplicationContainer(
        ingest_document=ingest,
        retire_document=retire,
        get_document=get,
        list_documents=list_docs,
        research_service_factory=research,
    )


@lru_cache(maxsize=1)
def resolve_application() -> Tuple[ApplicationContainer, AdapterRegistry]:
    """Initialise the application container and adapter registry."""

    registry = AdapterRegistry()
    registry.register("settings", get_settings)
    registry.register("engine", get_engine)
    registry.register(
        "research_notes_repository_factory",
        SqlAlchemyResearchNoteRepositoryFactory,
    )
    registry.register(
        "hypotheses_repository_factory",
        SqlAlchemyHypothesisRepositoryFactory,
    )

    def _build_research_service_factory() -> Callable[[Session], ResearchService]:
        from theo.domain.research import fetch_dss_links

        notes_factory = registry.resolve("research_notes_repository_factory")
        hypotheses_factory = registry.resolve("hypotheses_repository_factory")

        def _factory(session: Session) -> ResearchService:
            notes_repository = notes_factory(session)
            hypotheses_repository = hypotheses_factory(session)
            return ResearchService(
                notes_repository,
                hypothesis_repository=hypotheses_repository,
                fetch_dss_links_func=fetch_dss_links,
            )

        return _factory

    registry.register("research_service_factory", _build_research_service_factory)

    def _build_reasoner_factory() -> Callable[[Session], NeighborhoodReasoner]:
        def _factory(session: Session) -> NeighborhoodReasoner:
            return NeighborhoodReasoner()

        return _factory

    registry.register("reasoner_factory", _build_reasoner_factory)

    def _build_embedding_rebuild_service() -> EmbeddingRebuildService:
        from theo.infrastructure.api.app.ingest.embeddings import (
            clear_embedding_cache,
            get_embedding_service,
        )
        from theo.infrastructure.api.app.ingest.sanitizer import sanitize_passage_text

        embedding_service = get_embedding_service()

        def _session_factory() -> Session:
            engine = registry.resolve("engine")
            return Session(engine)

        def _repository_factory(session: Session):
            return SQLAlchemyPassageEmbeddingRepository(session)

        return EmbeddingRebuildService(
            session_factory=_session_factory,
            repository_factory=_repository_factory,
            embedding_service=embedding_service,
            sanitize_text=sanitize_passage_text,
            cache_clearer=clear_embedding_cache,
        )

    embedding_rebuild_service = _build_embedding_rebuild_service()
    registry.register(
        "embedding_rebuild_service", lambda: embedding_rebuild_service
    )

    def _build_ingest_callable() -> Callable[[Document], DocumentId]:
        return lambda document: _ingest_document(registry, document)

    def _build_retire_callable() -> Callable[[DocumentId], None]:
        return lambda document_id: _retire_document(registry, document_id)

    def _build_get_callable() -> Callable[[DocumentId], Document | None]:
        return lambda document_id: _get_document(registry, document_id)

    def _build_list_callable() -> Callable[..., list[Document]]:
        def _runner(*, limit: int = 20) -> list[Document]:
            return _list_documents(registry, limit=limit)

        return _runner

    container = bootstrap_application(
        registry=registry,
        command_factory=_build_ingest_callable,
        retire_factory=_build_retire_callable,
        get_factory=_build_get_callable,
        list_factory=_build_list_callable,
        research_factory=_build_research_service_factory,
    )
    return container, registry


__all__ = [
    "bootstrap_application",
    "resolve_application",
    "_document_from_record",
    "_extract_language",
    "_extract_scripture_refs",
    "_extract_tags",
    "_get_document",
    "_ingest_document",
    "_list_documents",
    "_retire_document",
    "_session_scope",
]

