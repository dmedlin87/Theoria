"""Optimized tests for Celery worker tasks with performance improvements."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import httpx
import pytest
from celery.exceptions import Retry
from sqlalchemy.orm import Session

from celery.app.task import Task

pytest_plugins = ("celery.contrib.pytest",)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.adapters.persistence.models import (  # noqa: E402
    ChatSession,
    Document,
    IngestionJob,
    Passage,
)

try:  # noqa: E402 - optional dependency handling
    from theo.services.api.app.ai.rag import RAGCitation
except ModuleNotFoundError:
    @dataclass(slots=True)
    class RAGCitation:
        index: int
        osis: str
        anchor: str
        passage_id: str = ""
        document_id: str = ""
        document_title: str = ""
        snippet: str = ""
        source_url: str = ""

try:  # noqa: E402
    from theo.services.api.app.models.ai import ChatMemoryEntry
except ModuleNotFoundError:
    @dataclass(slots=True)
    class ChatMemoryEntry:
        question: str | None = None
        answer: str = ""
        answer_summary: str | None = None
        citations: list = None
        document_ids: list = None
        created_at: datetime | None = None

        @classmethod
        def model_validate(cls, payload: dict[str, Any]) -> "ChatMemoryEntry":
            return cls(**payload)
            
        def model_dump(self, **kwargs) -> dict[str, Any]:
            return {
                "question": self.question,
                "answer": self.answer,
                "answer_summary": self.answer_summary,
                "citations": self.citations or [],
                "document_ids": self.document_ids or [],
                "created_at": self.created_at.isoformat() if self.created_at else None
            }

try:  # noqa: E402
    from theo.services.api.app.models.search import HybridSearchFilters, HybridSearchResult
except ModuleNotFoundError:
    @dataclass(slots=True)
    class HybridSearchFilters:
        collection: str | None = None
        tags: list[str] | None = None

        @classmethod
        def model_validate(cls, payload: dict[str, Any]) -> "HybridSearchFilters":
            return cls(**payload)

        def model_dump(self, *, exclude_none: bool = False) -> dict[str, Any]:
            data = {"collection": self.collection, "tags": self.tags}
            return {k: v for k, v in data.items() if v is not None} if exclude_none else data

    @dataclass(slots=True)
    class HybridSearchResult:
        id: str
        document_id: str
        text: str
        osis_ref: str | None = None
        page_no: int | None = None
        score: float = 0.0
        document_title: str | None = None
        snippet: str | None = None
        rank: int = 1
        raw_text: str | None = None
        start_char: int | None = None
        end_char: int | None = None
        t_start: float | None = None
        t_end: float | None = None
        meta: dict = None
        
        def __post_init__(self):
            if self.meta is None:
                self.meta = {}

from theo.services.api.app.workers import tasks  # noqa: E402


def _task(obj: Any) -> Task:
    """Return a Celery task with typing information."""
    return cast(Task, obj)


class TestWorkerTasksOptimized:
    """Optimized test class for worker tasks."""
    
    @pytest.fixture(autouse=True)
    def setup_mocks(self, monkeypatch):
        """Setup common mocks for all tests."""
        # Mock heavy pipeline operations
        mock_document = Document(
            id="test-doc",
            title="Test Document",
            collection="Test Collection",
            source_type="test"
        )
        
        monkeypatch.setattr(
            "theo.services.api.app.ingest.pipeline.run_pipeline_for_url",
            MagicMock(return_value=mock_document)
        )
        monkeypatch.setattr(
            "theo.services.api.app.ingest.pipeline.run_pipeline_for_file", 
            MagicMock(return_value=mock_document)
        )
        
        # Mock enrichment operations
        monkeypatch.setattr(
            "theo.services.api.app.enrich.MetadataEnricher.enrich_document",
            MagicMock(return_value=True)
        )
        
        # Mock deliverable building
        from theo.services.api.app.models.export import DeliverablePackage, DeliverableManifest, DeliverableAsset
        mock_manifest = DeliverableManifest(
            export_id="test-export",
            schema_version="1",
            generated_at=datetime.now(UTC),
            type="sermon",
            filters={}
        )
        mock_asset = DeliverableAsset(
            format="markdown",
            filename="test.md", 
            media_type="text/markdown",
            content="test content"
        )
        mock_package = DeliverablePackage(
            manifest=mock_manifest,
            assets=[mock_asset]
        )
        
        monkeypatch.setattr(
            "theo.services.api.app.ai.rag.deliverables.generate_sermon_prep_outline",
            MagicMock(return_value={})
        )
        monkeypatch.setattr(
            "theo.services.api.app.ai.rag.exports.build_sermon_deliverable",
            MagicMock(return_value=mock_package)
        )
        
    def test_process_url_basic_functionality(self, worker_engine):
        """Test URL processing with minimal database operations."""
        with patch('theo.services.api.app.ingest.pipeline.run_pipeline_for_url') as mock_pipeline:
            mock_doc = Document(
                id="url-test",
                title="URL Test Doc", 
                collection="Test",
                channel="Test Channel"
            )
            mock_pipeline.return_value = mock_doc
            
            # Execute task
            _task(tasks.process_url).run(
                "doc-123",
                "https://example.com/test",
                frontmatter={"title": "Test"}
            )
            
            # Verify pipeline was called
            assert mock_pipeline.called
            
    def test_process_url_with_job_tracking(self, worker_engine):
        """Test job status updates during URL processing."""
        # Create test job
        with Session(worker_engine) as session:
            job = IngestionJob(job_type="url_ingest", status="queued")
            session.add(job)
            session.commit()
            job_id = job.id
        
        with patch('theo.services.api.app.ingest.pipeline.run_pipeline_for_url') as mock_pipeline:
            mock_doc = Document(id="job-test", title="Job Test")
            mock_pipeline.return_value = mock_doc
            
            _task(tasks.process_url).run(
                "doc-job-123",
                "https://example.com/job-test", 
                job_id=job_id
            )
            
        # Verify job completion
        with Session(worker_engine) as session:
            updated_job = session.get(IngestionJob, job_id)
            assert updated_job.status == "completed"
            
    def test_validate_citations_fast(self, worker_engine, monkeypatch):
        """Fast citation validation test with minimal setup."""
        # Setup test data efficiently
        now = datetime.now(UTC)
        citation = RAGCitation(index=1, osis="John.3.16", anchor="page 1")
        entry = ChatMemoryEntry(
            question="Test question?",
            answer="Test answer",
            citations=[citation],
            created_at=now
        )
        
        with Session(worker_engine) as session:
            chat_session = ChatSession(
                id="test-session",
                user_id="test-user", 
                memory_snippets=[entry.model_dump()],
                created_at=now,
                updated_at=now,
                last_interaction_at=now
            )
            session.add(chat_session)
            session.commit()
            
        # Mock search to return matching results
        def mock_search(session, request):
            return [HybridSearchResult(
                id="passage-1",
                document_id="doc-1",
                text="Test passage",
                osis_ref="John.3.16",
                page_no=1
            )]
            
        monkeypatch.setattr("theo.services.api.app.workers.tasks.hybrid_search", mock_search)
        
        # Run validation
        result = _task(tasks.validate_citations).run(limit=1)
        
        assert result["sessions"] == 1
        assert result["entries"] >= 1
        
    def test_refresh_hnsw_mocked(self, monkeypatch):
        """Test HNSW refresh with database operations mocked."""
        executed_statements = []
        
        class MockConnection:
            def execute(self, statement):
                executed_statements.append(str(statement))
                return MagicMock(scalars=lambda: MagicMock(all=lambda: []))
                
        class MockEngine:
            def begin(self):
                return MockConnection()
                
        monkeypatch.setattr(tasks, "get_engine", lambda: MockEngine())
        monkeypatch.setattr(
            tasks, "_evaluate_hnsw_recall", 
            lambda *args, **kwargs: {"sample_size": 5, "avg_recall": 0.95}
        )
        
        result = _task(tasks.refresh_hnsw).run()
        
        # Verify SQL execution
        assert any("DROP INDEX" in stmt for stmt in executed_statements)
        assert any("CREATE INDEX" in stmt for stmt in executed_statements) 
        assert any("ANALYZE" in stmt for stmt in executed_statements)
        assert result["sample_size"] == 5
        
    def test_build_deliverable_minimal(self, tmp_path, monkeypatch):
        """Test deliverable building with minimal file I/O."""
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.storage_root = tmp_path
        monkeypatch.setattr(tasks, "settings", mock_settings)
        
        # Mock file operations
        with patch('pathlib.Path.mkdir') as mock_mkdir, \
             patch('pathlib.Path.write_text') as mock_write_text:
            
            result = _task(tasks.build_deliverable).run(
                export_type="sermon",
                formats=["markdown"],
                export_id="test-export",
                topic="Test Topic"
            )
            
            assert result["export_id"] == "test-export"
            assert result["status"] == "completed"
            assert len(result["assets"]) >= 1
            
            # Verify file operations were called
            assert mock_mkdir.called
            assert mock_write_text.called
