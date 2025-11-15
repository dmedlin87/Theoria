"""Test fixtures for worker tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import sqlite3
from types import SimpleNamespace
from typing import Any, Iterable, Sequence
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys

import pytest
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
try:  # pragma: no cover - SQLAlchemy module path changed across releases
    from sqlalchemy.pool import StaticPool
except (ImportError, AttributeError):  # pragma: no cover
    from sqlalchemy import pool as _sa_pool

    StaticPool = _sa_pool.StaticPool  # type: ignore[attr-defined]

from theo.adapters.persistence.models import Document
from theo.application.facades.database import Base, configure_engine, get_engine
from theo.infrastructure.api.app.workers import tasks


@pytest.fixture(scope="session")
def fast_worker_engine(tmp_path_factory: pytest.TempPathFactory):
    """Create a SQLite engine optimised for the current platform."""
    if sys.platform.startswith("win"):
        db_dir = tmp_path_factory.mktemp("worker-fast-db")
        db_path = Path(db_dir) / "worker.db"
        database_url = f"sqlite:///{db_path}"
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
    else:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="module")
def worker_db_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a reusable SQLite template with all tables migrated."""
    db_dir = tmp_path_factory.mktemp("worker-template")
    template_path = Path(db_dir) / "template.db"
    configure_engine(f"sqlite:///{template_path}")
    engine = get_engine()
    Base.metadata.create_all(engine)
    engine.dispose()
    return template_path


@pytest.fixture
def worker_engine(fast_worker_engine):
    """Use fast in-memory engine instead of file-based database."""
    yield fast_worker_engine


@pytest.fixture
def worker_session(worker_engine) -> Session:
    """Yield a SQLAlchemy session bound to the fast worker database."""
    with Session(worker_engine) as session:
        yield session


@pytest.fixture(autouse=True)
def mock_heavy_operations(monkeypatch):
    """Mock expensive operations to speed up tests."""
    # Avoid patching pathlib.Path globally to keep pytest tmp_path working
    
    # Mock HTTP requests
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    try:
        import httpx as _httpx  # type: ignore
    except ModuleNotFoundError:  # pragma: no cover - optional dependency
        _httpx = None

    if _httpx is not None and hasattr(_httpx, "post"):
        monkeypatch.setattr(_httpx, "post", MagicMock(return_value=mock_response))
    
    # Mock expensive analytics operations
    mock_snapshot = MagicMock()
    mock_snapshot.nodes = []
    mock_snapshot.edges = []
    mock_snapshot.generated_at = None
    monkeypatch.setattr(
        "theo.infrastructure.api.app.analytics.topic_map.TopicMapBuilder.build",
        MagicMock(return_value=mock_snapshot)
    )
    
    # Mock vector operations
    monkeypatch.setattr(
        "theo.infrastructure.api.app.workers.tasks._format_vector", 
        lambda x: [0.1] * 10
    )
    
    # Mock telemetry to reduce overhead
    monkeypatch.setattr(
        "theo.application.facades.telemetry.log_workflow_event", 
        MagicMock()
    )
    monkeypatch.setattr(
        "theo.application.facades.telemetry.record_counter", 
        MagicMock()
    )


@pytest.fixture(autouse=True)
def optimize_celery_config():
    """Configure Celery for fastest possible test execution."""
    original_conf = dict(tasks.celery.conf)
    
    # Optimize for speed
    tasks.celery.conf.update(
        task_always_eager=True,
        task_eager_propagates=True, 
        task_store_eager_result=False,
        task_ignore_result=True,
        worker_prefetch_multiplier=1,
        task_acks_late=False,
        worker_disable_rate_limits=True,
        broker_transport_options={'visibility_timeout': 1},
    )
    
    yield
    
    # Restore original config
    tasks.celery.conf.clear()
    tasks.celery.conf.update(original_conf)


@pytest.fixture(autouse=True)
def _bind_worker_engine(worker_engine, monkeypatch):
    """Ensure worker tasks use the in-memory engine by default."""

    monkeypatch.setattr(tasks, "get_engine", lambda: worker_engine)
    yield


class WorkerStubContext:
    """Provide deterministic stand-ins for external worker dependencies."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, worker_engine) -> None:
        self._monkeypatch = monkeypatch
        self._engine = worker_engine
        self._db_path = (
            Path(worker_engine.url.database).resolve()
            if worker_engine.url.database
            else None
        )
        self._original_deps = tasks.get_worker_dependencies()
        self._dependency_stubs: dict[str, Any] = {
            "run_pipeline_for_file": self._run_pipeline_for_file,
            "run_pipeline_for_url": self._run_pipeline_for_url,
            "hybrid_search": self._hybrid_search,
            "build_citations": self._build_citations,
            "validate_model_completion": self._validate_model_completion,
        }
        self.pipeline_calls: list[dict[str, Any]] = []
        self.job_status_updates: list[dict[str, Any]] = []
        self.notification_calls: list[dict[str, Any]] = []
        self.watchlist_calls: list[dict[str, Any]] = []
        self._hybrid_results: Sequence[Any] = []
        self._original_update_job_status = tasks._update_job_status

        tasks.configure_worker_dependencies(**self._dependency_stubs)
        self._monkeypatch.setattr(tasks, "_update_job_status", self._track_job_status)
        self._monkeypatch.setattr(
            tasks,
            "topic_digest_notifier",
            SimpleNamespace(delay=self._record_notification),
        )
        self._monkeypatch.setattr(
            tasks,
            "watchlist_alert_queue",
            SimpleNamespace(delay=self._record_watchlist),
        )
        self._monkeypatch.setattr(
            tasks,
            "generate_topic_digest",
            lambda session, window_start: SimpleNamespace(
                generated_at=datetime.now(UTC),
                topics=[SimpleNamespace(topic="Digest Topic", document_ids=["source-doc"])],
            ),
        )
        self._monkeypatch.setattr(
            tasks,
            "store_topic_digest",
            lambda session, digest: None,
        )

        def _fake_upsert_digest_document(session: Session, digest: Any) -> Document:
            document = Document(
                id=f"digest-{len(self.notification_calls) + 1}",
                title="Digest Document",
                source_type="digest",
                collection="Digest",  # type: ignore[arg-type]
                bib_json={"clusters": [{"document_ids": ["source-doc"]}]},
                topics=[topic.topic for topic in getattr(digest, "topics", [])],
            )
            session.add(document)
            session.flush()
            return document

        self._monkeypatch.setattr(tasks, "upsert_digest_document", _fake_upsert_digest_document)

    def restore(self) -> None:
        tasks.configure_worker_dependencies(
            run_pipeline_for_file=self._original_deps.run_pipeline_for_file,
            run_pipeline_for_url=self._original_deps.run_pipeline_for_url,
            hybrid_search=self._original_deps.hybrid_search,
            build_citations=self._original_deps.build_citations,
            validate_model_completion=self._original_deps.validate_model_completion,
        )

    def _ensure_document(
        self,
        session: Session,
        identifier: str,
        *,
        frontmatter: dict[str, Any] | None,
        source_type: str,
        source_url: str | None,
    ) -> Document:
        frontmatter = frontmatter or {}
        document = session.get(Document, identifier)
        if document is None:
            document = Document(
                id=identifier,
                title=frontmatter.get("title") or f"Stub Document {identifier}",
                collection=frontmatter.get("collection") or "Stub Collection",
                channel=frontmatter.get("channel") or "Theo Channel",
                source_type=source_type,
                source_url=source_url,
            )
            session.add(document)
        else:
            if "title" in frontmatter:
                document.title = frontmatter["title"]
            if "collection" in frontmatter:
                document.collection = frontmatter["collection"]
            if "channel" in frontmatter:
                document.channel = frontmatter["channel"]
        session.flush()
        return document

    def _run_pipeline_for_url(
        self,
        session: Session,
        url: str,
        *,
        source_type: str | None = None,
        frontmatter: dict[str, Any] | None = None,
        dependencies: Any = None,
    ) -> Document:
        identifier = None
        if frontmatter:
            identifier = frontmatter.get("id") or frontmatter.get("document_id")
        if not identifier:
            identifier = url

        document = self._ensure_document(
            session,
            identifier,
            frontmatter=frontmatter,
            source_type=source_type or "url",
            source_url=url,
        )
        self.pipeline_calls.append(
            {
                "kind": "url",
                "url": url,
                "frontmatter": frontmatter or {},
                "document_id": document.id,
            }
        )
        return document

    def _run_pipeline_for_file(
        self,
        session: Session,
        path: Path,
        frontmatter: dict[str, Any] | None = None,
        *,
        dependencies: Any = None,
    ) -> Document:
        identifier = None
        if frontmatter:
            identifier = frontmatter.get("id") or frontmatter.get("document_id")
        if not identifier:
            identifier = str(path)
        document = self._ensure_document(
            session,
            identifier,
            frontmatter=frontmatter,
            source_type="file",
            source_url=str(path),
        )
        self.pipeline_calls.append(
            {
                "kind": "file",
                "path": str(path),
                "frontmatter": frontmatter or {},
                "document_id": document.id,
            }
        )
        return document

    def _hybrid_search(
        self,
        _session: Session,
        _request: Any,
    ) -> Sequence[Any]:
        return list(self._hybrid_results)

    def set_hybrid_results(self, results: Iterable[Any]) -> None:
        self._hybrid_results = list(results)

    def _build_citations(self, results: Sequence[Any]) -> Sequence[Any]:
        citations: list[Any] = []
        for index, result in enumerate(results, start=1):
            page = getattr(result, "page_no", None)
            anchor = f"page {page}" if page is not None else "unknown"
            citations.append(
                tasks.RAGCitation(
                    index=index,
                    osis=getattr(result, "osis_ref", "") or "",
                    anchor=anchor,
                    passage_id=getattr(result, "id", ""),
                    document_id=getattr(result, "document_id", ""),
                    document_title=getattr(result, "document_title", "") or "",
                    snippet=getattr(result, "snippet", "") or "",
                    source_url=f"/doc/{getattr(result, 'document_id', '')}#passage-{getattr(result, 'id', '')}",
                )
            )
        return citations

    def _validate_model_completion(
        self,
        completion: str,
        expected: Sequence[tasks.RAGCitation],
    ) -> None:
        sources_section = completion.split("Sources:")[-1]
        anchors: dict[int, str] = {}
        for part in sources_section.split(";"):
            part = part.strip()
            if not part or not part.startswith("["):
                continue
            try:
                index_str, remainder = part.split("]", 1)
                index = int(index_str.strip("["))
                anchor = remainder.split("(", 1)[1].rsplit(")", 1)[0]
            except Exception:
                continue
            anchors[index] = anchor.strip()
        for citation in expected:
            if anchors.get(citation.index) != citation.anchor:
                raise tasks.GuardrailError(
                    f"Citation {citation.index} anchor mismatch: {anchors.get(citation.index)!r}"
                )

    def _track_job_status(
        self,
        _session: Session,
        job_id: str,
        *,
        status: str,
        error: str | None = None,
        document_id: str | None = None,
    ) -> None:
        self.job_status_updates.append(
            {
                "job_id": job_id,
                "status": status,
                "error": error,
                "document_id": document_id,
            }
        )
        if self._db_path is not None:
            assignments = ["status = ?", "updated_at = ?"]
            params: list[Any] = [status, datetime.now(UTC).isoformat()]
            if error is not None:
                assignments.append("error = ?")
                params.append(error)
            if document_id is not None:
                assignments.append("document_id = ?")
                params.append(document_id)
            params.append(job_id)
            statement = f"UPDATE ingestion_jobs SET {', '.join(assignments)} WHERE id = ?"
            with sqlite3.connect(self._db_path, check_same_thread=False) as conn:
                conn.execute(statement, params)
                conn.commit()
            return

        with Session(self._engine) as session:
            self._original_update_job_status(
                session,
                job_id,
                status=status,
                error=error,
                document_id=document_id,
            )

    def _record_notification(self, *args: Any, **kwargs: Any) -> None:
        self.notification_calls.append({"args": args, "kwargs": kwargs})

    def _record_watchlist(self, *args: Any, **kwargs: Any) -> None:
        self.watchlist_calls.append({"args": args, "kwargs": kwargs})

    @contextmanager
    def override_dependencies(self, **overrides: Any):
        tasks.configure_worker_dependencies(**overrides)
        try:
            yield
        finally:
            # Use list() to avoid "dictionary changed size during iteration" errors
            resets = {
                key: self._dependency_stubs[key]
                for key in list(overrides.keys())
                if key in self._dependency_stubs
            }
            if resets:
                tasks.configure_worker_dependencies(**resets)


@pytest.fixture
def worker_stubs(
    monkeypatch: pytest.MonkeyPatch, worker_engine
) -> WorkerStubContext:
    """Expose the worker stub context to tests that need fine-grained control."""
    context = WorkerStubContext(monkeypatch, worker_engine)
    try:
        yield context
    finally:
        context.restore()
