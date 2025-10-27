"""Test fixtures for worker tests."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from theo.application.facades.database import Base, configure_engine, get_engine
from theo.infrastructure.api.app.workers import tasks


@pytest.fixture(scope="session")
def fast_worker_engine():
    """Create an in-memory SQLite engine for fast worker tests."""
    # Use in-memory SQLite with connection pooling for maximum speed
    engine = create_engine(
        "sqlite:///:memory:", 
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False  # Disable SQL logging for speed
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


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
    # Mock file I/O operations  
    monkeypatch.setattr("pathlib.Path.mkdir", MagicMock())
    monkeypatch.setattr("pathlib.Path.write_text", MagicMock())
    monkeypatch.setattr("pathlib.Path.write_bytes", MagicMock())
    
    # Mock HTTP requests
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    monkeypatch.setattr("httpx.post", MagicMock(return_value=mock_response))
    
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
