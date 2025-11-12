"""Performance-optimized patches for worker tests."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch, Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.application.facades.database import Base
from theo.adapters.persistence.models import Document, IngestionJob, Passage, ChatSession
from theo.infrastructure.api.app.workers import tasks

pytestmark = pytest.mark.usefixtures("worker_stubs")

# Performance optimization fixtures
@pytest.fixture(scope="session")
def fast_test_engine():
    """Ultra-fast in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False  # Critical: disable SQL logging
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)

@pytest.fixture
def optimized_session(fast_test_engine):
    """Optimized database session with automatic rollback."""
    SessionLocal = sessionmaker(bind=fast_test_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

@pytest.fixture(autouse=True)
def mock_expensive_operations(monkeypatch):
    """Automatically mock all expensive operations."""
    # Mock HTTP operations
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.status_code = 200
    mock_response.json = Mock(return_value={})
    
    monkeypatch.setattr("httpx.post", Mock(return_value=mock_response))
    monkeypatch.setattr("httpx.get", Mock(return_value=mock_response))
    
    # Mock file operations
    monkeypatch.setattr("pathlib.Path.mkdir", Mock())
    monkeypatch.setattr("pathlib.Path.write_text", Mock())
    monkeypatch.setattr("pathlib.Path.write_bytes", Mock())
    monkeypatch.setattr("pathlib.Path.read_text", Mock(return_value="mock content"))
    monkeypatch.setattr("pathlib.Path.exists", Mock(return_value=True))
    monkeypatch.setattr("pathlib.Path.is_file", Mock(return_value=True))
    
    # Mock analytics operations
    mock_snapshot = Mock()
    mock_snapshot.nodes = []
    mock_snapshot.edges = []
    mock_snapshot.generated_at = datetime.now(UTC)
    
    monkeypatch.setattr(
        "theo.infrastructure.api.app.analytics.topic_map.TopicMapBuilder.build",
        Mock(return_value=mock_snapshot)
    )
    
    # Mock vector operations
    monkeypatch.setattr(
        "theo.infrastructure.api.app.workers.tasks._format_vector",
        Mock(return_value=[0.1] * 10)
    )
    
    # Mock enrichment
    monkeypatch.setattr(
        "theo.infrastructure.api.app.enrich.MetadataEnricher.enrich_document",
        Mock(return_value=True)
    )
    
    # Mock telemetry
    monkeypatch.setattr(
        "theo.application.facades.telemetry.log_workflow_event", Mock()
    )
    monkeypatch.setattr(
        "theo.application.facades.telemetry.record_counter", Mock()
    )

@pytest.fixture(autouse=True)
def optimize_celery_for_tests():
    """Configure Celery for maximum test speed."""
    original_config = dict(tasks.celery.conf)
    
    # Ultra-fast configuration
    tasks.celery.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
        task_store_eager_result=False,
        task_ignore_result=True,
        worker_prefetch_multiplier=1,
        task_acks_late=False,
        worker_disable_rate_limits=True,
        broker_transport_options={'visibility_timeout': 1},
        result_expires=1,
    )
    
    yield
    
    # Restore original config
    tasks.celery.conf.clear()
    tasks.celery.conf.update(original_config)

# Helper functions for fast test setup
def create_test_document(session: Session, doc_id: str = "test-doc") -> Document:
    """Quickly create a test document."""
    doc = Document(
        id=doc_id,
        title="Test Document",
        collection="Test Collection",
        source_type="test"
    )
    session.add(doc)
    session.flush()
    return doc

def create_test_job(session: Session, job_type: str = "test") -> IngestionJob:
    """Quickly create a test job."""
    job = IngestionJob(job_type=job_type, status="queued")
    session.add(job)
    session.flush()
    return job

# Optimized test implementations
class TestWorkerPerformance:
    """Performance-optimized worker tests."""
    
    def test_process_url_fast(self, optimized_session):
        """Fast URL processing test."""
        with patch('theo.infrastructure.api.app.workers.tasks.get_engine') as mock_engine:
            mock_engine.return_value = optimized_session.bind
            
            # This should complete in <100ms instead of several seconds
            result = tasks.process_url(
                "doc-123",
                "https://example.com/test",
                frontmatter={"title": "Fast Test"}
            )
            
            # Verify it ran without errors
            assert result is None  # Task completed successfully
    
    def test_process_url_with_job_fast(self, optimized_session):
        """Fast job tracking test."""
        job = create_test_job(optimized_session, "url_ingest")
        optimized_session.commit()
        
        with patch('theo.infrastructure.api.app.workers.tasks.get_engine') as mock_engine:
            mock_engine.return_value = optimized_session.bind
            
            tasks.process_url(
                "doc-job-123",
                "https://example.com/job-test",
                job_id=job.id
            )
            
            # Verify job was updated
            optimized_session.refresh(job)
            assert job.status == "completed"
    
    def test_validate_citations_fast(self, optimized_session, worker_stubs):
        """Fast citation validation test."""
        # Create minimal test data
        chat_session = ChatSession(
            id="fast-session",
            user_id="test-user",
            memory_snippets=[
                {
                    "question": "Test question?",
                    "answer": "Test answer",
                    "citations": [
                        {
                            "index": 1,
                            "osis": "John.3.16", 
                            "anchor": "page 1"
                        }
                    ]
                }
            ],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            last_interaction_at=datetime.now(UTC)
        )
        optimized_session.add(chat_session)
        optimized_session.commit()
        
        with patch('theo.infrastructure.api.app.workers.tasks.get_engine') as mock_engine:

            mock_engine.return_value = optimized_session.bind
            worker_stubs.set_hybrid_results([
                Mock(
                    id="passage-1",
                    document_id="doc-1",
                    text="Test passage",
                    osis_ref="John.3.16",
                    page_no=1
                )
            ])

            result = tasks.validate_citations(limit=1)
            
            assert result["sessions"] == 1
            assert result["entries"] >= 1
    
    def test_refresh_hnsw_fast(self):
        """Fast HNSW refresh test with complete mocking."""
        executed_statements = []
        
        class MockConnection:
            def execute(self, statement):
                executed_statements.append(str(statement))
                return Mock(scalars=lambda: Mock(all=lambda: []))
        
        class MockEngine:
            def begin(self):
                return MockConnection()
        
        with patch('theo.infrastructure.api.app.workers.tasks.get_engine') as mock_get_engine, \
             patch('theo.infrastructure.api.app.workers.tasks._evaluate_hnsw_recall') as mock_eval:
            
            mock_get_engine.return_value = MockEngine()
            mock_eval.return_value = {"sample_size": 5, "avg_recall": 0.95}
            
            result = tasks.refresh_hnsw()
            
            # Verify operations completed
            assert any("DROP INDEX" in stmt for stmt in executed_statements)
            assert any("CREATE INDEX" in stmt for stmt in executed_statements)
            assert result["sample_size"] == 5

# Performance test to measure improvements
@pytest.mark.performance
class TestPerformanceMetrics:
    """Tests to measure actual performance improvements."""
    
    def test_timing_comparison(self, optimized_session, benchmark=None):
        """Measure performance improvements."""
        if benchmark is None:
            # Fallback for when pytest-benchmark isn't available
            import time
            start = time.perf_counter()
            
            tasks.process_url(
                "timing-test",
                "https://example.com/timing"
            )
            
            end = time.perf_counter()
            duration = end - start
            
            # Should complete in under 100ms with optimizations
            assert duration < 0.1, f"Test took {duration:.3f}s, expected < 0.1s"
        else:
            # Use pytest-benchmark if available
            result = benchmark(
                tasks.process_url,
                "benchmark-test", 
                "https://example.com/benchmark"
            )
            assert result is None

if __name__ == "__main__":
    # Quick validation that imports work
    print("Performance patch loaded successfully")
    print(f"Tasks module: {tasks}")
    print("Ready for optimized testing!")
