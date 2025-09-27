from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.core.database import (  # noqa: E402  (import after path tweak)
    Base,
    configure_engine,
    get_engine,
)
from theo.services.api.app.main import app  # noqa: E402
from theo.services.api.app.workers import tasks  # noqa: E402


def test_refresh_hnsw_job_endpoint_enqueues(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "jobs.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    captured: dict[str, object] = {}

    class DummyResult:
        id = "task-id"

    def fake_delay(job_id: str, sample_queries: int = 25, top_k: int = 10):
        captured["job_id"] = job_id
        captured["sample_queries"] = sample_queries
        captured["top_k"] = top_k
        return DummyResult()

    monkeypatch.setattr(tasks.refresh_hnsw, "delay", fake_delay)

    with TestClient(app) as client:
        response = client.post(
            "/jobs/refresh-hnsw",
            json={"sample_queries": 5, "top_k": 3},
        )

    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["job_type"] == "refresh_hnsw"
    assert payload["payload"]["sample_queries"] == 5
    assert payload["payload"]["top_k"] == 3
    assert captured["job_id"] == payload["id"]
    assert captured["sample_queries"] == 5
    assert captured["top_k"] == 3
