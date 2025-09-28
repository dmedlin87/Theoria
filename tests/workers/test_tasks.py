"""Tests for Celery worker tasks."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.core.database import (  # noqa: E402  (import after path tweak)
    Base,
    configure_engine,
    get_engine,
    get_settings,
)
from theo.services.api.app.db.models import (  # noqa: E402
    Document,
    IngestionJob,
    Passage,
)
from theo.services.api.app.workers import tasks  # noqa: E402


def test_process_url_ingests_fixture_url(tmp_path) -> None:
    """The URL worker ingests a YouTube fixture without raising."""

    db_path = tmp_path / "test.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.create_all(engine)

    settings = get_settings()
    original_storage = settings.storage_root
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    settings.storage_root = storage_root

    try:
        frontmatter = {
            "title": "Custom Theo Title",
            "collection": "Custom Collection",
        }
        tasks.process_url.run(
            "doc-123",
            "https://youtu.be/sample_video",
            frontmatter=frontmatter,
        )
    finally:
        settings.storage_root = original_storage

    with Session(engine) as session:
        documents = session.query(Document).all()

    assert len(documents) == 1
    document = documents[0]
    assert document.title == "Custom Theo Title"
    assert document.collection == "Custom Collection"
    assert document.channel == "Theo Channel"


def test_process_url_updates_job_status_and_document_id(tmp_path) -> None:
    """URL ingestion jobs transition status and persist the ingested document."""

    db_path = tmp_path / "job.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.create_all(engine)

    settings = get_settings()
    original_storage = settings.storage_root
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    settings.storage_root = storage_root

    with Session(engine) as session:
        job = IngestionJob(job_type="url_ingest", status="queued")
        session.add(job)
        session.commit()
        job_id = job.id

    status_transitions: list[str] = []
    original_update = tasks._update_job_status
    original_retry = tasks.process_url.retry

    def tracking_update(
        session: Session,
        job_id_param: str,
        *,
        status: str,
        error: str | None = None,
        document_id: str | None = None,
    ) -> None:
        if job_id_param == job_id:
            status_transitions.append(status)
        original_update(
            session,
            job_id_param,
            status=status,
            error=error,
            document_id=document_id,
        )

    retry_calls: list[tuple[tuple, dict]] = []

    def fail_retry(*args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        retry_calls.append((args, kwargs))
        raise AssertionError("process_url.retry should not be called during successful ingestion")

    tasks._update_job_status = tracking_update
    tasks.process_url.retry = fail_retry

    try:
        frontmatter = {
            "title": "Job Status Theo Title",
            "collection": "Job Collection",
        }
        tasks.process_url.run(
            "doc-job-123",
            "https://youtu.be/sample_video",
            frontmatter=frontmatter,
            job_id=job_id,
        )
    finally:
        tasks._update_job_status = original_update
        tasks.process_url.retry = original_retry
        settings.storage_root = original_storage

    with Session(engine) as session:
        job_record = session.get(IngestionJob, job_id)
        assert job_record is not None
        document_id = job_record.document_id
        document = session.get(Document, document_id) if document_id else None

    assert status_transitions[:1] == ["processing"]
    assert status_transitions[-1:] == ["completed"]
    assert job_record.status == "completed"
    assert job_record.document_id is not None
    assert document is not None
    assert document.title == "Job Status Theo Title"
    assert retry_calls == []


def test_enrich_document_populates_metadata(tmp_path) -> None:
    """Metadata enrichment hydrates bibliographic fields from fixtures."""

    db_path = tmp_path / "enrich.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        document = Document(
            title="Theo Engine Sample Work",
            source_type="pdf",
            source_url="https://doi.org/10.1234/sample",
            sha256="sample-sha",
        )
        session.add(document)
        session.commit()
        document_id = document.id

    tasks.enrich_document.run(document_id)

    with Session(engine) as session:
        enriched = session.get(Document, document_id)

    assert enriched is not None
    assert enriched.doi == "10.1234/sample"
    assert enriched.authors == ["Alice Example", "Bob Example"]
    assert enriched.venue == "Journal of Theo Research"
    assert enriched.year == 2022
    assert enriched.abstract == "theo engine research"
    assert enriched.topics == {
        "primary": "Theology",
        "all": ["Theology", "Information Retrieval"],
    }
    assert enriched.enrichment_version == 1
    assert isinstance(enriched.bib_json, dict)
    assert (
        enriched.bib_json.get("enrichment", {}).get("openalex", {}).get("id")
        == "https://openalex.org/W123456789"
    )
    assert enriched.bib_json.get("primary_topic") == "Theology"


def test_topic_digest_worker_updates_job_status(tmp_path) -> None:
    db_path = tmp_path / "topic.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        source = Document(
            id="source-doc",
            title="Digest Source",
            source_type="markdown",
            bib_json={"primary_topic": "Digest Topic"},
        )
        session.add(source)
        job = IngestionJob(job_type="topic_digest", status="queued")
        session.add(job)
        session.commit()
        job_id = job.id

    captured: dict[str, Any] = {}

    def fake_delay(
        document_id: str, recipients: list[str], context: dict[str, Any] | None = None
    ):
        captured["document_id"] = document_id
        captured["recipients"] = recipients
        captured["context"] = context or {}

    original_delay = tasks.send_topic_digest_notification.delay
    tasks.send_topic_digest_notification.delay = fake_delay
    try:
        tasks.topic_digest.run(hours=1, job_id=job_id, notify=["alerts@example.com"])
    finally:
        tasks.send_topic_digest_notification.delay = original_delay

    with Session(engine) as session:
        updated = session.get(IngestionJob, job_id)
        digest_doc = (
            session.query(Document)
            .filter(Document.source_type == "digest")
            .order_by(Document.created_at.desc())
            .first()
        )

    assert updated is not None
    assert updated.status == "completed"
    assert digest_doc is not None
    assert digest_doc.topics and "Digest Topic" in digest_doc.topics
    assert digest_doc.bib_json["clusters"][0]["document_ids"] == ["source-doc"]
    assert captured["recipients"] == ["alerts@example.com"]
    assert captured["document_id"] == digest_doc.id
    assert "Digest Topic" in captured["context"].get("topics", [])


def test_generate_document_summary_creates_summary_document(tmp_path) -> None:
    db_path = tmp_path / "summary.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        document = Document(
            title="Creation Sermon",
            source_type="markdown",
            abstract="In the beginning was the Word.",
            bib_json={"primary_topic": "Creation", "topics": ["John", "Logos"]},
        )
        session.add(document)
        session.commit()
        document_id = document.id

        session.add(
            Passage(
                document_id=document_id,
                page_no=1,
                start_char=0,
                end_char=120,
                text="In the beginning God created the heavens and the earth.",
            )
        )
        job = IngestionJob(job_type="summary", status="queued")
        session.add(job)
        session.commit()
        job_id = job.id

    tasks.generate_document_summary.run(document_id=document_id, job_id=job_id)

    with Session(engine) as session:
        summary_doc = (
            session.query(Document)
            .filter(Document.source_type == "ai_summary")
            .order_by(Document.created_at.desc())
            .first()
        )
        job_record = session.get(IngestionJob, job_id)

    assert summary_doc is not None
    assert summary_doc.bib_json["generated_from"] == document_id
    assert summary_doc.topics == ["Creation", "John", "Logos"]
    assert job_record is not None and job_record.status == "completed"
    assert job_record.document_id == summary_doc.id


def test_refresh_hnsw_executes_rebuild_sql(monkeypatch) -> None:
    executed: list[str] = []

    class DummyResult:
        def scalars(self):
            return self

        def all(self):
            return []

    class DummyConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, statement):
            executed.append(str(statement))
            return DummyResult()

    class DummyEngine:
        def begin(self):
            return DummyConnection()

    dummy_engine = DummyEngine()

    monkeypatch.setattr(tasks, "get_engine", lambda: dummy_engine)
    monkeypatch.setattr(
        tasks,
        "_evaluate_hnsw_recall",
        lambda *args, **kwargs: {"sample_size": 0},
    )

    metrics = tasks.refresh_hnsw.run()

    assert any(
        "DROP INDEX IF EXISTS ix_passages_embedding_hnsw" in statement
        for statement in executed
    )
    assert any("USING hnsw" in statement for statement in executed)
    assert any("ANALYZE passages" in statement for statement in executed)
    assert metrics["sample_size"] == 0
