"""Regression tests for the generic job enqueue endpoint."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.application.facades import database as database_module
from theo.application.facades.database import (  # noqa: E402  (import after path tweak)
    Base,
    configure_engine,
    get_engine,
)
from theo.services.api.app.main import app  # noqa: E402
from theo.services.api.app.routes import jobs as jobs_module  # noqa: E402


def test_repro_enqueue_job_runtime_error(monkeypatch, tmp_path) -> None:
    """New jobs should not crash when Celery returns a task identifier."""

    db_path = tmp_path / "jobs.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    try:
        class DummyResult:
            id = "dummy-task-id"

        def fake_send_task(task_name: str, kwargs: dict | None = None, eta=None):
            return DummyResult()

        monkeypatch.setattr(jobs_module.celery, "send_task", fake_send_task)

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/jobs/enqueue",
                json={"task": "tests.example", "args": {"foo": "bar"}},
            )

        assert response.status_code == 202, response.text
    finally:
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]
