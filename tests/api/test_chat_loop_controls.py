from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from theo.application.facades.database import get_session
from theo.services.api.app.ai.research_loop import ResearchLoopController
from theo.services.api.app.main import app
from theo.services.api.app.persistence_models import ChatSession
from theo.services.api.app.models.research_plan import ResearchPlanStepStatus


@pytest.fixture()
def _session_factory(api_engine):
    return sessionmaker(bind=api_engine, future=True)


@pytest.fixture()
def client(_session_factory) -> TestClient:
    def _override_session():
        with _session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_session, None)


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


def test_get_research_plan_returns_steps(client: TestClient) -> None:
    session_id = "plan-get-session"
    _create_chat_session(session_id)
    _initialise_loop_state(session_id)

    response = client.get(f"/ai/chat/{session_id}/plan")
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    steps = payload["steps"]
    assert isinstance(steps, list) and steps
    assert steps[0]["status"] == ResearchPlanStepStatus.IN_PROGRESS.value


def test_reorder_research_plan(client: TestClient) -> None:
    session_id = "plan-reorder-session"
    _create_chat_session(session_id)
    _initialise_loop_state(session_id)

    initial = client.get(f"/ai/chat/{session_id}/plan").json()
    steps = initial["steps"]
    order = [steps[-1]["id"], *[step["id"] for step in steps[:-1]]]
    response = client.patch(
        f"/ai/chat/{session_id}/plan/order",
        json={"order": order},
    )
    assert response.status_code == 200
    reordered = response.json()["steps"]
    assert reordered[0]["id"] == steps[-1]["id"]
    assert reordered[0]["index"] == 0


def test_update_research_plan_step(client: TestClient) -> None:
    session_id = "plan-update-session"
    _create_chat_session(session_id)
    _initialise_loop_state(session_id)

    initial = client.get(f"/ai/chat/{session_id}/plan").json()
    target = initial["steps"][0]
    response = client.patch(
        f"/ai/chat/{session_id}/plan/steps/{target['id']}",
        json={"query": "summaries on justification", "tool": "semantic_search"},
    )
    assert response.status_code == 200
    updated = response.json()
    step = next(item for item in updated["steps"] if item["id"] == target["id"])
    assert step["query"] == "summaries on justification"
    assert step["tool"] == "semantic_search"


def test_skip_research_plan_step(client: TestClient) -> None:
    session_id = "plan-skip-session"
    _create_chat_session(session_id)
    _initialise_loop_state(session_id)

    initial = client.get(f"/ai/chat/{session_id}/plan").json()
    target = initial["steps"][0]
    response = client.post(
        f"/ai/chat/{session_id}/plan/steps/{target['id']}/skip",
        json={"reason": "Handled during intake"},
    )
    assert response.status_code == 200
    payload = response.json()
    step = next(item for item in payload["steps"] if item["id"] == target["id"])
    assert step["status"] == ResearchPlanStepStatus.SKIPPED.value
    assert payload["active_step_id"] != target["id"]
