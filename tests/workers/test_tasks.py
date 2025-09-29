"""Tests for Celery worker tasks."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from sqlalchemy.orm import Session

from celery.app.task import Task

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
    ChatSession,
    Document,
    IngestionJob,
    Passage,
)
from theo.services.api.app.ai.rag import RAGCitation  # noqa: E402
from theo.services.api.app.models.ai import ChatMemoryEntry  # noqa: E402
from theo.services.api.app.models.search import HybridSearchResult  # noqa: E402
from theo.services.api.app.workers import tasks  # noqa: E402


def _task(obj: Any) -> Task:
    """Return a Celery task with typing information for static analysis."""

    return cast(Task, obj)


class _FakeMetric:
    def __init__(self) -> None:
        self.counts: dict[str, float] = {}

    class _Child:
        def __init__(self, parent: "_FakeMetric", status: str) -> None:
            self._parent = parent
            self._status = status

        def inc(self, amount: float = 1.0) -> None:
            self._parent.counts[self._status] = (
                self._parent.counts.get(self._status, 0.0) + amount
            )

    def labels(self, **labels: Any) -> "_FakeMetric._Child":
        status = labels.get("status", "unknown")
        return self._Child(self, str(status))


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
        _task(tasks.process_url).run(
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
    process_url_task = _task(tasks.process_url)
    original_retry = cast(Any, process_url_task.retry)

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
    setattr(process_url_task, "retry", fail_retry)

    try:
        frontmatter = {
            "title": "Job Status Theo Title",
            "collection": "Job Collection",
        }
        process_url_task.run(
            "doc-job-123",
            "https://youtu.be/sample_video",
            frontmatter=frontmatter,
            job_id=job_id,
        )
    finally:
        tasks._update_job_status = original_update
        setattr(process_url_task, "retry", original_retry)
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

    _task(tasks.enrich_document).run(document_id)

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


def test_enrich_document_missing_document_marks_job_failed(tmp_path, caplog) -> None:
    """When a document is missing the enrichment job is marked failed."""

    db_path = tmp_path / "missing_enrich.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        job = IngestionJob(job_type="enrich", status="queued")
        session.add(job)
        session.commit()
        job_id = job.id

    caplog.set_level("WARNING", logger="theo.services.api.app.workers.tasks")

    _task(tasks.enrich_document).run(document_id="missing", job_id=job_id)

    with Session(engine) as session:
        updated_job = session.get(IngestionJob, job_id)

    assert updated_job is not None
    assert updated_job.status == "failed"
    assert updated_job.error == "document not found"
    assert any(
        "Document not found for enrichment" in record.getMessage()
        for record in caplog.records
    )


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

    notification_task = _task(tasks.send_topic_digest_notification)
    original_delay = cast(Any, notification_task.delay)
    setattr(notification_task, "delay", fake_delay)
    try:
        _task(tasks.topic_digest).run(hours=1, job_id=job_id, notify=["alerts@example.com"])
    finally:
        setattr(notification_task, "delay", original_delay)

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
    digest_document = digest_doc
    assert digest_document.topics and "Digest Topic" in digest_document.topics
    assert digest_document.bib_json is not None
    assert digest_document.bib_json["clusters"][0]["document_ids"] == ["source-doc"]
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

    _task(tasks.generate_document_summary).run(document_id=document_id, job_id=job_id)

    with Session(engine) as session:
        summary_doc = (
            session.query(Document)
            .filter(Document.source_type == "ai_summary")
            .order_by(Document.created_at.desc())
            .first()
        )
        job_record = session.get(IngestionJob, job_id)

    assert summary_doc is not None
    generated_summary = summary_doc
    assert generated_summary.bib_json is not None
    assert generated_summary.bib_json["generated_from"] == document_id
    assert generated_summary.topics == ["Creation", "John", "Logos"]
    assert job_record is not None and job_record.status == "completed"
    completed_job = job_record
    assert completed_job.document_id == generated_summary.id


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

    metrics = _task(tasks.refresh_hnsw).run()

    assert any(
        "DROP INDEX IF EXISTS ix_passages_embedding_hnsw" in statement
        for statement in executed
    )
    assert any("USING hnsw" in statement for statement in executed)
    assert any("ANALYZE passages" in statement for statement in executed)
    assert metrics["sample_size"] == 0

def test_validate_citations_passes_and_updates_job(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "validate-success.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    now = datetime.now(UTC)
    citation = RAGCitation(
        index=1,
        osis="John.3.16",
        anchor="page 2",
        passage_id="passage-1",
        document_id="doc-1",
        document_title="Gospel of John",
        snippet="For God so loved the world",
        source_url="/doc/doc-1#passage-passage-1",
    )
    entry = ChatMemoryEntry(
        question="What does John 3:16 teach?",
        answer="For God so loved the world.",
        answer_summary="God loves the world",
        citations=[citation],
        document_ids=["doc-1"],
        created_at=now,
    )

    with Session(engine) as session:
        session_record = ChatSession(
            id="session-success",
            user_id="user-1",
            stance=None,
            summary=entry.answer_summary,
            memory_snippets=[entry.model_dump(mode="json")],
            document_ids=entry.document_ids,
            preferences=None,
            created_at=now,
            updated_at=now,
            last_interaction_at=now,
        )
        job = IngestionJob(job_type="validate_citations", status="queued")
        session.add_all([session_record, job])
        session.commit()
        job_id = job.id

    def fake_hybrid_search(_: Session, __: Any) -> list[HybridSearchResult]:
        return [
            HybridSearchResult(
                id="passage-1",
                document_id="doc-1",
                text="For God so loved the world",
                raw_text=None,
                osis_ref="John.3.16",
                start_char=None,
                end_char=None,
                page_no=2,
                t_start=None,
                t_end=None,
                score=0.9,
                meta={},
                document_title="Gospel of John",
                snippet="For God so loved the world",
                rank=1,
            )
        ]

    metric = _FakeMetric()
    monkeypatch.setattr(tasks, "CITATION_DRIFT_EVENTS", metric)
    monkeypatch.setattr(tasks, "hybrid_search", fake_hybrid_search)

    result = _task(tasks.validate_citations).run(job_id=job_id, limit=1)

    assert result["passed"] == 1
    assert result["failed"] == 0
    assert result["discrepancies"] == []
    assert metric.counts == {"passed": 1.0}

    with Session(engine) as session:
        job_record = session.get(IngestionJob, job_id)
        assert job_record is not None
        assert job_record.status == "completed"
        assert job_record.payload is not None
        assert job_record.payload.get("passed") == 1
        assert job_record.payload.get("limit") == 1


def test_validate_citations_logs_mismatch(monkeypatch, tmp_path, caplog) -> None:
    db_path = tmp_path / "validate-failure.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    now = datetime.now(UTC)
    citation = RAGCitation(
        index=1,
        osis="John.3.16",
        anchor="page 2",
        passage_id="passage-1",
        document_id="doc-1",
        document_title="Gospel of John",
        snippet="For God so loved the world",
        source_url="/doc/doc-1#passage-passage-1",
    )
    entry = ChatMemoryEntry(
        question="What does John 3:16 teach?",
        answer="For God so loved the world.",
        citations=[citation],
        document_ids=["doc-1"],
        created_at=now,
    )

    with Session(engine) as session:
        session_record = ChatSession(
            id="session-failure",
            user_id="user-2",
            stance=None,
            summary=entry.answer,
            memory_snippets=[entry.model_dump(mode="json")],
            document_ids=entry.document_ids,
            preferences=None,
            created_at=now,
            updated_at=now,
            last_interaction_at=now,
        )
        session.add(session_record)
        session.commit()

    def mismatched_search(_: Session, __: Any) -> list[HybridSearchResult]:
        return [
            HybridSearchResult(
                id="passage-1",
                document_id="doc-1",
                text="For God so loved the world",
                raw_text=None,
                osis_ref="John.3.16",
                start_char=None,
                end_char=None,
                page_no=3,
                t_start=None,
                t_end=None,
                score=0.9,
                meta={},
                document_title="Gospel of John",
                snippet="For God so loved the world",
                rank=1,
            )
        ]

    metric = _FakeMetric()
    monkeypatch.setattr(tasks, "CITATION_DRIFT_EVENTS", metric)
    monkeypatch.setattr(tasks, "hybrid_search", mismatched_search)

    caplog.set_level("WARNING")
    result = _task(tasks.validate_citations).run(limit=1)

    assert result["failed"] == 1
    assert result["passed"] == 0
    assert metric.counts == {"failed": 1.0}
    assert result["discrepancies"]
    assert result["discrepancies"][0]["status"] == "failed"
    assert "Citation validation mismatch" in caplog.text
