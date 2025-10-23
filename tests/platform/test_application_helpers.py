"""Tests for helper functions in ``theo.platform.application``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from theo.adapters import AdapterRegistry
from theo.adapters.persistence import models
from theo.domain import Document, DocumentId, DocumentMetadata
from theo.platform import application as application_module


@pytest.fixture
def engine() -> Engine:
    """Provide an in-memory SQLite engine shared across sessions."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        models.Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def registry(engine: Engine) -> AdapterRegistry:
    """Construct an adapter registry wired with the in-memory engine."""

    registry = AdapterRegistry()
    registry.register("engine", lambda: engine)
    return registry


@pytest.fixture
def session(engine: Engine) -> Session:
    """Yield a transactional SQLAlchemy session for direct model inspection."""

    with Session(engine) as session:
        yield session


def test_extract_language_prefers_language_key() -> None:
    record = models.Document(id="doc-lang", bib_json={"language": "English", "lang": "en"})
    assert application_module._extract_language(record) == "English"

    record.bib_json = {"lang": "es"}
    assert application_module._extract_language(record) == "es"

    record.bib_json = {"language": 42}
    assert application_module._extract_language(record) is None


def test_extract_tags_combines_topics_and_payload() -> None:
    record = models.Document(
        id="doc-tags",
        topics=["theology", "ethics", "theology"],
        bib_json={"tags": ["grace", "love", "grace"]},
    )
    assert application_module._extract_tags(record) == [
        "theology",
        "ethics",
        "grace",
        "love",
    ]

    record.topics = {"primary": "atonement", "secondary": "atonement"}
    record.bib_json = {"tags": ["atonement", "incarnation"]}
    assert application_module._extract_tags(record) == [
        "atonement",
        "incarnation",
    ]


def test_extract_scripture_refs_merges_stored_and_passages(session: Session) -> None:
    record = models.Document(
        id="doc-refs",
        bib_json={"scripture_refs": ["John.3.16", "John.3.16"]},
    )
    session.add(record)
    session.flush()

    session.add_all(
        [
            models.Passage(
                document_id=record.id,
                page_no=2,
                t_start=1.0,
                start_char=50,
                osis_ref="Rom.8.1",
                text="Second passage",
            ),
            models.Passage(
                document_id=record.id,
                page_no=1,
                t_start=0.5,
                start_char=10,
                osis_ref="Rom.8.2",
                text="First passage",
            ),
            models.Passage(
                document_id=record.id,
                page_no=3,
                t_start=0.1,
                start_char=5,
                osis_ref="John.3.16",
                text="Duplicate reference",
            ),
        ]
    )
    session.commit()

    refs = application_module._extract_scripture_refs(session, record)
    assert refs == ("John.3.16", "Rom.8.2", "Rom.8.1")


def test_document_from_record_builds_domain_model(session: Session) -> None:
    created = datetime(2024, 1, 1, 12, 0, 0)
    updated = created + timedelta(hours=1)

    record = models.Document(
        id="doc-record",
        title=None,
        collection="sermons",
        source_type=None,
        created_at=created,
        updated_at=updated,
        sha256="checksum",
        topics=["grace", "hope"],
        bib_json={"language": "en", "tags": ["grace", "joy"]},
    )
    session.add(record)
    session.add(
        models.Passage(
            document_id=record.id,
            page_no=1,
            t_start=0.0,
            start_char=0,
            osis_ref="John.1.1",
            text="In the beginning",
        )
    )
    session.commit()

    document = application_module._document_from_record(session, record)
    assert document.id == DocumentId("doc-record")
    assert document.metadata.title == "doc-record"
    assert document.metadata.source == "sermons"
    assert document.metadata.language == "en"
    assert document.metadata.created_at == created
    assert document.metadata.updated_at == updated
    assert document.tags == ("grace", "hope", "joy")
    assert document.scripture_refs == ("John.1.1",)
    assert document.checksum == "checksum"


def test_ingest_document_persists_metadata_and_merges_tags(
    registry: AdapterRegistry, engine
) -> None:
    created = datetime.now(UTC)
    updated = created + timedelta(days=1)

    document = Document(
        id=DocumentId("doc-ingest"),
        metadata=DocumentMetadata(
            title="Doc Title",
            source="sermons",
            language="en",
            created_at=created,
            updated_at=updated,
        ),
        scripture_refs=("John.3.16", "Rom.8.1"),
        tags=("grace", "hope"),
        checksum="abc123",
    )

    application_module._ingest_document(registry, document)

    with Session(engine) as check_session:
        record = check_session.get(models.Document, "doc-ingest")
        assert record is not None
        assert record.title == "Doc Title"
        assert record.collection == "sermons"
        assert record.source_type == "graphql"
        assert record.sha256 == "abc123"
        assert record.bib_json["language"] == "en"
        assert record.bib_json["scripture_refs"] == ["John.3.16", "Rom.8.1"]
        assert record.bib_json["tags"] == ["grace", "hope"]
        assert record.topics == ["grace", "hope"]

    updated_document = Document(
        id=document.id,
        metadata=DocumentMetadata(
            title="Doc Title",
            source="sermons",
            language=None,
        ),
        scripture_refs=("Rom.8.1", "Gal.2.20"),
        tags=("hope", "faith"),
        checksum="abc123",
    )

    application_module._ingest_document(registry, updated_document)

    with Session(engine) as check_session:
        record = check_session.get(models.Document, "doc-ingest")
        assert record is not None
        assert record.bib_json["language"] == "en"
        assert record.bib_json["scripture_refs"] == [
            "Rom.8.1",
            "Gal.2.20",
        ]
        assert record.bib_json["tags"] == ["grace", "hope", "faith"]
        assert record.topics == ["grace", "hope", "faith"]


def test_get_document_returns_domain_model(
    registry: AdapterRegistry, engine
) -> None:
    document = Document(
        id=DocumentId("doc-get"),
        metadata=DocumentMetadata(title="Title", source="archive", language="en"),
        scripture_refs=("John.3.16",),
        tags=("grace",),
    )
    application_module._ingest_document(registry, document)

    retrieved = application_module._get_document(registry, document.id)
    assert retrieved is not None
    assert retrieved.id == document.id
    assert retrieved.metadata.title == "Title"
    assert retrieved.metadata.source == "archive"
    assert retrieved.scripture_refs == ("John.3.16",)
    assert retrieved.tags == ("grace",)

    missing = application_module._get_document(registry, DocumentId("missing"))
    assert missing is None


def test_list_documents_orders_by_recency(registry: AdapterRegistry, engine) -> None:
    now = datetime.now(UTC)
    with Session(engine) as populate:
        populate.add_all(
            [
                models.Document(
                    id="doc-old",
                    title="Old",
                    collection="archive",
                    created_at=now - timedelta(days=5),
                    updated_at=now - timedelta(days=5),
                    bib_json={"language": "en"},
                ),
                models.Document(
                    id="doc-new",
                    title="New",
                    collection="archive",
                    created_at=now - timedelta(days=1),
                    updated_at=now - timedelta(days=1),
                    bib_json={"language": "en"},
                ),
                models.Document(
                    id="doc-latest",
                    title="Latest",
                    collection="archive",
                    created_at=now,
                    updated_at=now,
                    bib_json={"language": "en"},
                ),
            ]
        )
        populate.commit()

    listed = application_module._list_documents(registry, limit=2)
    assert [doc.id for doc in listed] == [DocumentId("doc-latest"), DocumentId("doc-new")]

    limited = application_module._list_documents(registry, limit=-5)
    assert len(limited) == 1
    assert limited[0].id == DocumentId("doc-latest")


def test_retire_document_removes_records(
    registry: AdapterRegistry, engine
) -> None:
    document = Document(
        id=DocumentId("doc-retire"),
        metadata=DocumentMetadata(title="Title", source="archive"),
        scripture_refs=(),
    )
    application_module._ingest_document(registry, document)

    application_module._retire_document(registry, document.id)

    with Session(engine) as check_session:
        assert check_session.get(models.Document, "doc-retire") is None
