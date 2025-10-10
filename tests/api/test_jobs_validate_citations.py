import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.core import database as database_module  # noqa: E402
from theo.services.api.app.core.database import (  # noqa: E402
    Base,
    configure_engine,
    get_engine,
)
from theo.services.api.app.main import app  # noqa: E402
from theo.services.api.app.workers import tasks  # noqa: E402


def test_validate_citations_job_endpoint_enqueues(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "jobs.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    try:
        captured: dict[str, object] = {}

        class DummyResult:
            id = "task-id"

        def fake_delay(job_id: str, limit: int = 25):
            captured["job_id"] = job_id
            captured["limit"] = limit
            return DummyResult()

        monkeypatch.setattr(tasks.validate_citations, "delay", fake_delay)

        with TestClient(app) as client:
            response = client.post(
                "/jobs/validate_citations",
                json={"limit": 7},
            )

        assert response.status_code == 202, response.text
        payload = response.json()
        assert payload["job_type"] == "validate_citations"
        assert payload["payload"]["limit"] == 7
        assert captured["job_id"] == payload["id"]
        assert captured["limit"] == 7
    finally:
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]


def test_validate_citations_job_uses_default_limit(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "jobs-default.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    try:
        captured: dict[str, object] = {}

        class DummyResult:
            id = "task-id"

        def fake_delay(job_id: str, limit: int = 25):
            captured["job_id"] = job_id
            captured["limit"] = limit
            return DummyResult()

        monkeypatch.setattr(tasks.validate_citations, "delay", fake_delay)

        with TestClient(app) as client:
            response = client.post("/jobs/validate_citations", json={})

        assert response.status_code == 202, response.text
        payload = response.json()
        assert payload["payload"]["limit"] == 25
        assert captured["job_id"] == payload["id"]
        assert captured["limit"] == 25
    finally:
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]

