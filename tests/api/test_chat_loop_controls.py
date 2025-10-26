from __future__ import annotations

import gc
import importlib
import importlib.util
import shutil
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from theo.application.facades.database import get_session
from theo.services.api.app.ai.research_loop import ResearchLoopController
from theo.services.api.app.main import app
from theo.services.api.app.models.research_plan import ResearchPlanStepStatus
from theo.services.api.app.persistence_models import ChatSession


_ujson_spec = importlib.util.find_spec("ujson")
if _ujson_spec is not None:
    ujson = importlib.import_module("ujson")
else:
    import json as ujson


@pytest.fixture(scope="session")
def shared_api_engine_pool(tmp_path_factory, _api_engine_template):
    pool = []
    for index in range(4):
        database_path = tmp_path_factory.mktemp(f"chat-loop-pool-{index}") / "api.sqlite"
        shutil.copy2(_api_engine_template, database_path)
        pool.append(database_path)
    return pool


@pytest.fixture(scope="module")
def persistent_session_factory(shared_api_engine_pool):
    database_path = shared_api_engine_pool[0]
    engine = create_engine(
        f"sqlite:///{database_path}",
        future=True,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    factory = sessionmaker(bind=engine, future=True)
    try:
        yield factory
    finally:
        engine.dispose()


@pytest.fixture(scope="module")
def batch_prepared_sessions(persistent_session_factory):
    sessions_data = {
        "loop-pause-session": {"partial": None},
        "loop-stop-session": {
            "partial": "Draft response on justification by faith.",
        },
        "loop-step-session": {"partial": None},
        "plan-get-session": {"partial": None},
        "plan-reorder-session": {"partial": None},
        "plan-update-session": {"partial": None},
        "plan-skip-session": {"partial": None},
    }

    with persistent_session_factory() as db_session:
        now = datetime.now(UTC)

        for session_id in sessions_data:
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

        controller = ResearchLoopController(db_session)
        for session_id, config in sessions_data.items():
            controller.initialise(session_id, question="What is justification?")
            if config["partial"] is not None:
                controller.set_partial_answer(
                    session_id,
                    config["partial"],
                    commit=False,
                )

        db_session.commit()

    return tuple(sessions_data.keys())


@pytest.fixture(scope="module")
def persistent_client(
    persistent_session_factory, batch_prepared_sessions
) -> TestClient:
    def _override_session():
        with persistent_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    test_client = TestClient(app)
    test_client.timeout = 5.0
    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture(scope="module")
def cached_payloads():
    return {
        "pause": ujson.dumps({"action": "pause"}),
        "stop": ujson.dumps({"action": "stop"}),
        "step": ujson.dumps({"action": "step"}),
    }


@pytest.fixture(autouse=True)
def cleanup_test_objects():
    yield
    gc.collect()


def assert_loop_state(response, expected_status: int, expected_state: str | None = None):
    assert response.status_code == expected_status
    payload = response.json()
    if expected_state is not None:
        assert payload["state"]["status"] == expected_state
    return payload


def assert_research_plan_structure(
    payload, session_id: str, expected_step_count: int | None = None
):
    assert payload["session_id"] == session_id
    steps = payload["steps"]
    assert isinstance(steps, list) and steps
    if expected_step_count is not None:
        assert len(steps) == expected_step_count
    return steps


@pytest.mark.xdist_group(name="loop_controls_group_1")
def test_loop_control_pause_updates_state(
    persistent_client: TestClient, cached_payloads
) -> None:
    session_id = "loop-pause-session"

    response = persistent_client.post(
        f"/ai/chat/{session_id}/loop/control",
        data=cached_payloads["pause"],
        headers={"Content-Type": "application/json"},
    )
    assert_loop_state(response, expected_status=200, expected_state="paused")

    follow_up = persistent_client.get(f"/ai/chat/{session_id}/loop")
    follow_up_payload = assert_loop_state(follow_up, expected_status=200)
    assert follow_up_payload["status"] == "paused"


@pytest.mark.xdist_group(name="loop_controls_group_2")
def test_loop_control_stop_returns_partial_answer(
    persistent_client: TestClient, cached_payloads
) -> None:
    session_id = "loop-stop-session"

    response = persistent_client.post(
        f"/ai/chat/{session_id}/loop/control",
        data=cached_payloads["stop"],
        headers={"Content-Type": "application/json"},
    )
    payload = assert_loop_state(response, expected_status=200, expected_state="stopped")
    assert payload["partial_answer"] is not None
    assert payload["partial_answer"].startswith("Draft response")


@pytest.mark.xdist_group(name="loop_controls_group_1")
def test_loop_control_step_advances_index(
    persistent_client: TestClient, cached_payloads
) -> None:
    session_id = "loop-step-session"

    response = persistent_client.post(
        f"/ai/chat/{session_id}/loop/control",
        data=cached_payloads["step"],
        headers={"Content-Type": "application/json"},
    )
    payload = assert_loop_state(response, expected_status=200)
    assert payload["state"]["status"] in {"running", "completed"}
    assert payload["state"]["current_step_index"] >= 1


@pytest.mark.xdist_group(name="loop_controls_group_2")
def test_get_research_plan_returns_steps(
    persistent_client: TestClient,
) -> None:
    session_id = "plan-get-session"

    response = persistent_client.get(f"/ai/chat/{session_id}/plan")
    payload = assert_loop_state(response, expected_status=200)
    steps = assert_research_plan_structure(payload, session_id)
    assert steps[0]["status"] == ResearchPlanStepStatus.IN_PROGRESS.value


@pytest.mark.xdist_group(name="loop_controls_group_1")
def test_reorder_research_plan(persistent_client: TestClient) -> None:
    session_id = "plan-reorder-session"

    initial = persistent_client.get(f"/ai/chat/{session_id}/plan").json()
    steps = initial["steps"]
    order = [steps[-1]["id"], *[step["id"] for step in steps[:-1]]]
    response = persistent_client.patch(
        f"/ai/chat/{session_id}/plan/order",
        json={"order": order},
    )
    reordered = assert_loop_state(response, expected_status=200)["steps"]
    assert reordered[0]["id"] == steps[-1]["id"]
    assert reordered[0]["index"] == 0


@pytest.mark.xdist_group(name="loop_controls_group_2")
def test_update_research_plan_step(persistent_client: TestClient) -> None:
    session_id = "plan-update-session"

    initial = persistent_client.get(f"/ai/chat/{session_id}/plan").json()
    target = initial["steps"][0]
    response = persistent_client.patch(
        f"/ai/chat/{session_id}/plan/steps/{target['id']}",
        json={"query": "summaries on justification", "tool": "semantic_search"},
    )
    updated = assert_loop_state(response, expected_status=200)
    step = next(item for item in updated["steps"] if item["id"] == target["id"])
    assert step["query"] == "summaries on justification"
    assert step["tool"] == "semantic_search"


@pytest.mark.xdist_group(name="loop_controls_group_1")
def test_skip_research_plan_step(persistent_client: TestClient) -> None:
    session_id = "plan-skip-session"

    initial = persistent_client.get(f"/ai/chat/{session_id}/plan").json()
    target = initial["steps"][0]
    response = persistent_client.post(
        f"/ai/chat/{session_id}/plan/steps/{target['id']}/skip",
        json={"reason": "Handled during intake"},
    )
    payload = assert_loop_state(response, expected_status=200)
    step = next(item for item in payload["steps"] if item["id"] == target["id"])
    assert step["status"] == ResearchPlanStepStatus.SKIPPED.value
