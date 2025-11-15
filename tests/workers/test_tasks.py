"""Tests for Celery worker tasks."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from celery.exceptions import Retry
from sqlalchemy.orm import Session

from celery.app.task import Task

pytest_plugins = ("celery.contrib.pytest",)

pytestmark = pytest.mark.usefixtures("worker_stubs")


@pytest.fixture
def celery_app():  # type: ignore[override]
    """Run Celery tasks eagerly against the application task registry."""

    app = tasks.celery
    original_always_eager = app.conf.task_always_eager
    original_propagates = app.conf.task_eager_propagates
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True
    try:
        yield app
    finally:
        app.conf.task_always_eager = original_always_eager
        app.conf.task_eager_propagates = original_propagates


@pytest.fixture(autouse=True)
def _stub_pythonbible(monkeypatch: pytest.MonkeyPatch):
    """Replace heavy pythonbible lookups with a lightweight stub during worker tests."""

    try:
        from theo.infrastructure.api.app.ingest import osis as ingest_osis
    except ModuleNotFoundError:  # pragma: no cover - dependency not installed
        yield
        return

    pb_module = getattr(ingest_osis, "pb", None)
    if pb_module is None:
        yield
        return

    monkeypatch.setattr(pb_module, "get_references", lambda _text: [], raising=False)
    monkeypatch.setattr(pb_module, "get_bible_book_id", lambda *_args, **_kwargs: None, raising=False)
    yield

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.application.facades.database import (  # noqa: E402  (import after path tweak)
    Base,
    configure_engine,
    get_engine,
    get_settings,
)
from theo.adapters.persistence.models import (  # noqa: E402
    ChatSession,
    Document,
    IngestionJob,
    Passage,
)

from theo.infrastructure.api.app.models.export import (  # noqa: E402
    DeliverableAsset,
    DeliverableManifest,
    DeliverablePackage,
)

try:  # noqa: E402 - optional dependency fallback for lightweight profiling
    from theo.infrastructure.api.app.ai.rag import RAGCitation
except ModuleNotFoundError:  # pragma: no cover - minimal fallback for lean environments
    @dataclass(slots=True)
    class RAGCitation:
        index: int
        osis: str
        anchor: str

try:  # noqa: E402 - optional dependency fallback for lightweight profiling
    from theo.infrastructure.api.app.models.ai import ChatMemoryEntry
except ModuleNotFoundError:  # pragma: no cover - minimal fallback for lean environments
    @dataclass(slots=True)
    class ChatMemoryEntry:
        question: str | None = None
        answer: str = ""
        answer_summary: str | None = None

        @classmethod
        def model_validate(cls, payload: dict[str, Any]) -> "ChatMemoryEntry":
            return cls(**payload)

        def model_dump(self, mode: str | None = None) -> dict[str, Any]:
            citations: list[dict[str, Any]] = []
            for citation in getattr(self, "citations", []) or []:
                if hasattr(citation, "model_dump"):
                    citations.append(citation.model_dump())
                elif hasattr(citation, "__dict__"):
                    citations.append({k: v for k, v in citation.__dict__.items() if not k.startswith("_")})
                else:
                    citations.append(citation)
            return {
                "question": self.question,
                "answer": self.answer,
                "answer_summary": self.answer_summary,
                "citations": citations,
                "document_ids": getattr(self, "document_ids", []) or [],
                "created_at": None,
            }

try:  # noqa: E402 - optional dependency fallback for lightweight profiling
    from theo.infrastructure.api.app.models.search import HybridSearchFilters, HybridSearchResult
except ModuleNotFoundError:  # pragma: no cover - minimal fallback for lean environments
    @dataclass(slots=True)
    class HybridSearchFilters:
        collection: str | None = None
        tags: list[str] | None = None

        @classmethod
        def model_validate(cls, payload: dict[str, Any]) -> "HybridSearchFilters":
            return cls(**payload)

        def model_dump(self, *, exclude_none: bool = False) -> dict[str, Any]:
            data = {"collection": self.collection, "tags": self.tags}
            if exclude_none:
                return {k: v for k, v in data.items() if v is not None}
            return data

    @dataclass(slots=True)
    class HybridSearchResult:
        document_id: str
        passage_id: str
        distance: float
        title: str | None = None
from theo.infrastructure.api.app.workers import tasks  # noqa: E402


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


def test_process_url_ingests_fixture_url(tmp_path, worker_engine) -> None:
    """The URL worker ingests a YouTube fixture without raising."""

    settings = get_settings()
    original_storage = settings.storage_root
    original_task_storage = tasks.settings.storage_root
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    settings.storage_root = storage_root
    tasks.settings.storage_root = storage_root

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
        tasks.settings.storage_root = original_task_storage

    with Session(worker_engine) as session:
        documents = session.query(Document).all()

    assert len(documents) == 1
    document = documents[0]
    assert document.title == "Custom Theo Title"
    assert document.collection == "Custom Collection"
    assert document.channel == "Theo Channel"


def test_process_url_updates_job_status_and_document_id(
    tmp_path, worker_engine, worker_stubs
) -> None:
    """URL ingestion jobs transition status and persist the ingested document."""

    settings = get_settings()
    original_storage = settings.storage_root
    original_task_storage = tasks.settings.storage_root
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    settings.storage_root = storage_root
    tasks.settings.storage_root = storage_root

    with Session(worker_engine) as session:
        job = IngestionJob(job_type="url_ingest", status="queued")
        session.add(job)
        session.commit()
        job_id = job.id

    process_url_task = _task(tasks.process_url)
    original_retry = cast(Any, process_url_task.retry)

    retry_calls: list[tuple[tuple, dict]] = []

    def fail_retry(*args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        retry_calls.append((args, kwargs))
        raise AssertionError("process_url.retry should not be called during successful ingestion")

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
        setattr(process_url_task, "retry", original_retry)
        settings.storage_root = original_storage

    with Session(worker_engine) as session:
        job_record = session.get(IngestionJob, job_id)
        assert job_record is not None
        document_id = job_record.document_id
        document = session.get(Document, document_id) if document_id else None

    job_events = [
        update["status"]
        for update in worker_stubs.job_status_updates
        if update["job_id"] == job_id
    ]
    assert job_events[:1] == ["processing"]
    assert job_events[-1:] == ["completed"]
    assert job_record.status == "completed"
    assert job_record.document_id is not None
    assert document is not None
    assert document.title == "Job Status Theo Title"
    assert retry_calls == []


def test_process_url_retries_with_backoff(
    monkeypatch: pytest.MonkeyPatch, worker_engine, celery_app, worker_stubs
) -> None:
    """Transient failures should trigger Celery retry with exponential backoff."""

    with Session(worker_engine) as session:
        job = IngestionJob(job_type="url_ingest", status="queued")
        session.add(job)
        session.commit()
        job_id = job.id

    retry_counts: list[int | None] = []

    def fake_compute_delay(retry_count: int | None) -> int:
        retry_counts.append(retry_count)
        return 42

    request = httpx.Request("GET", "https://example.com/fixture")
    response = httpx.Response(status_code=503, request=request)

    def failing_pipeline(*_: Any, **__: Any) -> None:
        raise httpx.HTTPStatusError("boom", request=request, response=response)

    monkeypatch.setattr(tasks, "_compute_retry_delay", fake_compute_delay)

    with worker_stubs.override_dependencies(run_pipeline_for_url=failing_pipeline):
        process_task = _task(tasks.process_url)
        with pytest.raises(Retry) as excinfo:
            process_task.apply(
                args=("doc-retry", "https://example.com/fixture"),
                kwargs={"job_id": job_id},
            )

    retry_exc = excinfo.value
    assert retry_exc.when == 42
    assert retry_counts == [0]
    assert retry_exc.sig.kwargs["job_id"] == job_id

    with Session(worker_engine) as session:
        job_record = session.get(IngestionJob, job_id)

    assert job_record is not None
    assert job_record.status == "failed"
    assert "boom" in (job_record.error or "")


def test_process_url_idempotent_completion(
    monkeypatch: pytest.MonkeyPatch, worker_engine, celery_app, worker_stubs
) -> None:
    """Successful retries should keep job metadata stable."""

    with Session(worker_engine) as session:
        job = IngestionJob(job_type="url_ingest", status="queued")
        session.add(job)
        session.commit()
        job_id = job.id

    call_counter = 0

    def stable_pipeline(
        session: Session,
        url: str,
        *,
        source_type: str | None = None,
        frontmatter: dict[str, Any] | None = None,
        dependencies: Any = None,
    ) -> Document:
        nonlocal call_counter
        call_counter += 1
        document = session.get(Document, "doc-stable")
        if document is None:
            document = Document(
                id="doc-stable",
                title="Stable Replay Document",
                collection="Retry Harness",
            )
            session.add(document)
            session.flush()
        return document

    with worker_stubs.override_dependencies(run_pipeline_for_url=stable_pipeline):
        process_task = _task(tasks.process_url)
        first = process_task.apply(
            args=("doc-stable", "https://example.com/replay"),
            kwargs={"job_id": job_id},
        )
        second = process_task.apply(
            args=("doc-stable", "https://example.com/replay"),
            kwargs={"job_id": job_id},
        )

    assert first.result is None
    assert second.result is None
    assert call_counter == 2

    with Session(worker_engine) as session:
        job_record = session.get(IngestionJob, job_id)
        document = session.get(Document, "doc-stable")

    assert job_record is not None
    assert job_record.status == "completed"
    assert job_record.document_id == "doc-stable"
    assert document is not None
    assert document.title == "Stable Replay Document"


def test_build_deliverable_task_writes_assets(monkeypatch, tmp_path, worker_engine) -> None:
    """Deliverable tasks persist manifests and assets under the export root."""

    settings = get_settings()
    original_storage = settings.storage_root
    original_task_storage = tasks.settings.storage_root
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    settings.storage_root = storage_root
    tasks.settings.storage_root = storage_root

    manifest = DeliverableManifest(
        export_id="sermon-initial",
        schema_version="1",
        generated_at=datetime.now(UTC),
        type="sermon",
        filters={"topic": "Hope"},
    )
    asset = DeliverableAsset(
        format="markdown",
        filename="sermon.md",
        media_type="text/markdown",
        content="---\nexport_id: sermon-initial\n",
    )
    package = DeliverablePackage(manifest=manifest, assets=[asset])

    def fake_outline(session: Session, **_: Any) -> object:
        return object()

    def fake_package(*_: Any, **__: Any) -> DeliverablePackage:
        return package

    monkeypatch.setattr(tasks, "generate_sermon_prep_outline", fake_outline)
    monkeypatch.setattr(tasks, "build_sermon_deliverable", fake_package)

    try:
        result = _task(tasks.build_deliverable).run(
            export_type="sermon",
            formats=["markdown"],
            export_id="sermon-export",
            topic="Hope",
            osis="John.1.1",
            filters={"collection": "Gospels"},
            model="echo",
            document_id=None,
        )
    finally:
        settings.storage_root = original_storage
        tasks.settings.storage_root = original_task_storage

    export_dir = storage_root / "exports" / "sermon-export"
    manifest_path = export_dir / "manifest.json"
    asset_path = export_dir / "sermon.md"

    assert export_dir.exists()
    assert manifest_path.is_file()
    assert asset_path.read_text(encoding="utf-8").startswith("---\nexport_id: sermon-initial")

    assert result["export_id"] == "sermon-export"
    assert result["manifest"]["export_id"] == "sermon-export"
    assert result["manifest_path"] == "/exports/sermon-export/manifest.json"
    assert result["assets"][0]["storage_path"] == "/exports/sermon-export/sermon.md"
    assert result["assets"][0]["size_bytes"] == len(asset.content.encode("utf-8"))


def test_enrich_document_populates_metadata(tmp_path, worker_engine) -> None:
    """Metadata enrichment hydrates bibliographic fields from fixtures."""

    with Session(worker_engine) as session:
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

    with Session(worker_engine) as session:
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


def test_enrich_document_missing_document_marks_job_failed(worker_engine, caplog) -> None:
    """When a document is missing the enrichment job is marked failed."""

    with Session(worker_engine) as session:
        job = IngestionJob(job_type="enrich", status="queued")
        session.add(job)
        session.commit()
        job_id = job.id

    caplog.set_level("WARNING", logger="theo.infrastructure.api.app.workers.tasks")

    _task(tasks.enrich_document).run(document_id="missing", job_id=job_id)

    with Session(worker_engine) as session:
        updated_job = session.get(IngestionJob, job_id)

    assert updated_job is not None
    assert updated_job.status == "failed"
    assert updated_job.error == "document not found"
    assert any(
        "Document not found for enrichment" in record.getMessage()
        for record in caplog.records
    )


def test_topic_digest_worker_updates_job_status(
    tmp_path, worker_engine, worker_stubs
) -> None:
    with Session(worker_engine) as session:
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

    _task(tasks.topic_digest).run(hours=1, job_id=job_id, notify=["alerts@example.com"])

    with Session(worker_engine) as session:
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
    assert worker_stubs.notification_calls
    last_notification = worker_stubs.notification_calls[-1]
    assert last_notification["args"][0] == digest_doc.id
    assert last_notification["args"][1] == ["alerts@example.com"]
    notification_context = last_notification["kwargs"].get("context")
    if notification_context is None and len(last_notification["args"]) >= 3:
        notification_context = last_notification["args"][2]
    assert notification_context is not None
    assert "Digest Topic" in notification_context.get("topics", [])


def test_generate_document_summary_creates_summary_document(worker_engine) -> None:
    with Session(worker_engine) as session:
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

    with Session(worker_engine) as session:
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

def test_validate_citations_passes_and_updates_job(
    monkeypatch, worker_engine, worker_stubs
) -> None:
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

    with Session(worker_engine) as session:
        snippet = entry.model_dump(mode="json")
        snippet["citations"] = [
            citation if isinstance(citation, dict) else getattr(citation, "model_dump", lambda: citation.__dict__)()
            for citation in snippet.get("citations", [])
        ]
        if isinstance(snippet.get("created_at"), datetime):
            snippet["created_at"] = snippet["created_at"].isoformat()

        session_record = ChatSession(
            id="session-success",
            user_id="user-1",
            stance=None,
            summary=entry.answer_summary,
            memory_snippets=[snippet],
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
    worker_stubs.set_hybrid_results(fake_hybrid_search(None, None))
    monkeypatch.setattr(tasks, "CITATION_DRIFT_EVENTS", metric)

    result = _task(tasks.validate_citations).run(job_id=job_id, limit=1)

    assert result["passed"] == 1
    assert result["failed"] == 0
    assert result["discrepancies"] == []
    assert metric.counts == {"passed": 1.0}

    with Session(worker_engine) as session:
        job_record = session.get(IngestionJob, job_id)
        assert job_record is not None
        assert job_record.status == "completed"
        assert job_record.payload is not None
        assert job_record.payload.get("passed") == 1
        assert job_record.payload.get("limit") == 1


def test_validate_citations_logs_mismatch(
    monkeypatch, worker_engine, caplog, worker_stubs
) -> None:
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

    with Session(worker_engine) as session:
        snippet = entry.model_dump(mode="json")
        snippet["citations"] = [
            citation if isinstance(citation, dict) else getattr(citation, "model_dump", lambda: citation.__dict__)()
            for citation in snippet.get("citations", [])
        ]
        if isinstance(snippet.get("created_at"), datetime):
            snippet["created_at"] = snippet["created_at"].isoformat()

        session_record = ChatSession(
            id="session-failure",
            user_id="user-2",
            stance=None,
            summary=entry.answer,
            memory_snippets=[snippet],
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
    worker_stubs.set_hybrid_results(mismatched_search(None, None))
    monkeypatch.setattr(tasks, "CITATION_DRIFT_EVENTS", metric)

    caplog.set_level("WARNING", logger="theo.infrastructure.api.app.workers.tasks")
    result = _task(tasks.validate_citations).run(limit=1)

    assert result["failed"] == 1
    assert result["passed"] == 0
    assert metric.counts == {"failed": 1.0}
    assert result["discrepancies"]
    assert result["discrepancies"][0]["status"] == "failed"
    assert "Citation validation mismatch" in caplog.text
