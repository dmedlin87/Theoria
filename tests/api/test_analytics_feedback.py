from __future__ import annotations

from pathlib import Path
from typing import Iterator
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.application.facades import database as database_module  # noqa: E402
from theo.application.facades.database import (  # noqa: E402
    Base,
    configure_engine,
    get_engine,
    get_session,
)
from theo.adapters.persistence.models import (  # noqa: E402
    FeedbackEvent,
    FeedbackEventAction,
)
from theo.infrastructure.api.app.main import app  # noqa: E402


@pytest.fixture()
def analytics_client(tmp_path: Path) -> Iterator[tuple[TestClient, Session]]:
    """Yield a TestClient connected to an isolated SQLite database."""

    configure_engine(f"sqlite:///{tmp_path / 'analytics.db'}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    def _override_session() -> Iterator[Session]:
        db = Session(engine)
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        app.dependency_overrides.pop(get_session, None)
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]


def test_feedback_endpoint_persists_event(analytics_client: tuple[TestClient, Session]) -> None:
    client, engine = analytics_client

    payload = {
        "action": "view",
        "user_id": "api-user",
        "chat_session_id": "chat-123",
        "query": "Tell me about Psalm 1",
        "document_id": "doc-42",
        "passage_id": "passage-99",
        "rank": 0,
        "score": 0.87,
        "confidence": 0.55,
    }

    response = client.post("/analytics/feedback", json=payload)

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"

    with Session(engine) as session:
        stored = session.query(FeedbackEvent).one()
        assert stored.action is FeedbackEventAction.VIEW
        assert stored.user_id == "api-user"
        assert stored.chat_session_id == "chat-123"
        assert stored.query == "Tell me about Psalm 1"
        assert stored.document_id == "doc-42"
        assert stored.passage_id == "passage-99"
        assert stored.rank == 0
        assert stored.score == pytest.approx(0.87)
        assert stored.confidence == pytest.approx(0.55)


def test_feedback_endpoint_rejects_invalid_action(
    analytics_client: tuple[TestClient, Session]
) -> None:
    client, engine = analytics_client

    response = client.post(
        "/analytics/feedback",
        json={"action": "invalid", "document_id": "doc-x"},
    )

    assert response.status_code == 400
    assert "Invalid feedback action" in response.json()["detail"]

    with Session(engine) as session:
        assert session.query(FeedbackEvent).count() == 0
