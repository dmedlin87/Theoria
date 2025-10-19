from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from theo.application.facades.database import get_session
from theo.services.api.app.ai.research_loop import ResearchLoopController
from theo.services.api.app.main import app
from theo.services.api.app.persistence_models import ChatSession


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _create_chat_session(session_id: str) -> None:
    session_gen = get_session()
    db_session = next(session_gen)
    try:
        now = datetime.now(UTC)
        record = ChatSession(
            id=session_id,
            user_id=None,
            stance=None,
            summary=None,
            memory_snippets=[],
            document_ids=[],
            goals=[],
            preferences={},
            created_at=now,
            updated_at=now,
            last_interaction_at=now,
        )
        db_session.merge(record)
        db_session.commit()
    finally:
        session_gen.close()


def _initialise_loop_state(session_id: str, *, partial: str | None = None) -> None:
    session_gen = get_session()
    db_session = next(session_gen)
    try:
        controller = ResearchLoopController(db_session)
        controller.initialise(session_id, question="What is justification?")
        if partial is not None:
            controller.set_partial_answer(session_id, partial, commit=True)
        db_session.commit()
    finally:
        session_gen.close()


def test_loop_control_pause_updates_state(client: TestClient) -> None:
    session_id = "loop-pause-session"
    _create_chat_session(session_id)
    _initialise_loop_state(session_id)

    response = client.post(
        f"/ai/chat/{session_id}/loop/control",
        json={"action": "pause"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["status"] == "paused"

    follow_up = client.get(f"/ai/chat/{session_id}/loop")
    assert follow_up.status_code == 200
    assert follow_up.json()["status"] == "paused"


def test_loop_control_stop_returns_partial_answer(client: TestClient) -> None:
    session_id = "loop-stop-session"
    _create_chat_session(session_id)
    _initialise_loop_state(session_id, partial="Draft response on justification by faith.")

    response = client.post(
        f"/ai/chat/{session_id}/loop/control",
        json={"action": "stop"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["status"] == "stopped"
    assert payload["partial_answer"] is not None
    assert payload["partial_answer"].startswith("Draft response")


def test_loop_control_step_advances_index(client: TestClient) -> None:
    session_id = "loop-step-session"
    _create_chat_session(session_id)
    _initialise_loop_state(session_id)

    response = client.post(
        f"/ai/chat/{session_id}/loop/control",
        json={"action": "step"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["status"] in {"running", "completed"}
    assert payload["state"]["current_step_index"] >= 1
