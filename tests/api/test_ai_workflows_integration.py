"""HTTP-level integration tests for /ai workflows."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from theo.services.api.app.ai import SermonPrepResponse, VerseCopilotResponse
from theo.services.api.app.ai.rag import RAGAnswer
from theo.application.facades.database import get_session
from theo.services.api.app.main import app
from theo.services.api.app.models.ai import (
    ChatSessionMessage,
    ChatSessionRequest,
    SermonPrepRequest,
    VerseCopilotRequest,
)
from theo.services.api.app.routes.ai.workflows import chat as chat_module
from theo.services.api.app.routes.ai.workflows import flows as flows_module


class _DummySession:
    """Lightweight stand-in for SQLAlchemy session objects."""

    def __init__(self) -> None:
        self._records: dict[tuple[type[object], str], object] = {}

    # SQLAlchemy Session API -------------------------------------------------
    def get(self, model: type[object], primary_key: str) -> object | None:  # noqa: D401
        return self._records.get((model, primary_key))

    def add(self, record: object) -> None:  # noqa: D401
        identifier = getattr(record, "id", None)
        if identifier is not None:
            self._records[(type(record), str(identifier))] = record

    def flush(self) -> None:  # noqa: D401 - included for API parity
        return None

    def commit(self) -> None:  # noqa: D401 - included for API parity
        return None


class _DummyRecorder:
    def finalize(self, **_: object) -> None:  # noqa: D401 - recorder protocol stub
        return None

    def log_step(self, **_: object) -> None:  # noqa: D401 - recorder protocol stub
        return None


class _DummyTrailService:
    def __init__(self, *_: object, **__: object) -> None:
        self.calls: list[dict[str, object]] = []

    @contextmanager
    def start_trail(self, *args: object, **kwargs: object) -> Iterator[_DummyRecorder]:
        _ = args
        self.calls.append(dict(kwargs))
        yield _DummyRecorder()


@pytest.fixture()
def api_client() -> Iterator[TestClient]:
    """Provide a FastAPI client with lightweight database overrides."""

    def _override_session() -> Iterator[_DummySession]:
        yield _DummySession()

    app.dependency_overrides[get_session] = _override_session  # type: ignore[assignment]
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_sermon_prep_route_uses_ai_service(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /ai/sermon-prep returns the orchestrated response payload."""

    answer = RAGAnswer(summary="Outline prepared", citations=[], model_output="Outline prepared")

    expected_response = SermonPrepResponse(
        topic="Hope",
        osis="John.3",
        outline=["Opening", "Body", "Closing"],
        key_points=["Proclaim hope"],
        answer=answer,
    )

    capture: dict[str, object] = {}

    def _fake_generate(session: object, *, topic: str, osis: str | None, filters: object, model_name: str | None, recorder=None, outline_template=None, key_points_limit=None):  # noqa: ANN001
        capture.update(
            {
                "session": session,
                "topic": topic,
                "osis": osis,
                "filters": filters,
                "model_name": model_name,
                "outline_template": outline_template,
                "key_points_limit": key_points_limit,
                "recorder": recorder,
            }
        )
        return expected_response

    monkeypatch.setattr(flows_module, "generate_sermon_prep_outline", _fake_generate)
    monkeypatch.setattr(flows_module, "TrailService", _DummyTrailService)

    payload = SermonPrepRequest(topic="Hope", osis="John.3")
    response = api_client.post("/ai/sermon-prep", json=payload.model_dump(mode="json"))

    assert response.status_code == 200
    body = response.json()
    assert body["outline"] == ["Opening", "Body", "Closing"]
    assert body["key_points"] == ["Proclaim hope"]
    assert body["answer"]["summary"] == "Outline prepared"
    assert capture["topic"] == "Hope"
    assert capture["osis"] == "John.3"


def test_verse_copilot_route_uses_ai_service(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /ai/verse returns grounded answer data."""

    answer = RAGAnswer(summary="In the beginning", citations=[], model_output="In the beginning")
    expected = VerseCopilotResponse(
        osis="John.1.1",
        question="What does it mean?",
        answer=answer,
        follow_ups=["Read the rest of John 1"],
    )

    def _fake_generate(*args: object, **kwargs: object):  # noqa: ANN401 - matching orchestrator signature
        _ = args, kwargs
        return expected

    monkeypatch.setattr(flows_module, "generate_verse_brief", _fake_generate)
    monkeypatch.setattr(flows_module, "TrailService", _DummyTrailService)

    payload = VerseCopilotRequest(osis="John.1.1", question="What does it mean?")
    response = api_client.post("/ai/verse", json=payload.model_dump(mode="json"))

    assert response.status_code == 200
    body = response.json()
    assert body["osis"] == "John.1.1"
    assert body["question"] == "What does it mean?"
    assert body["follow_ups"] == ["Read the rest of John 1"]
    assert body["answer"]["summary"] == "In the beginning"


def test_chat_route_streams_guarded_answer(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /ai/chat delegates to the guardrailed orchestrator."""

    answer = RAGAnswer(summary="Grace abounds", citations=[], model_output="Grace abounds")

    recorded_question: list[str] = []

    def _fake_guarded_chat(session: object, *, question: str, **_: object) -> RAGAnswer:  # noqa: ANN001
        recorded_question.append(question)
        assert isinstance(session, _DummySession)
        return answer

    monkeypatch.setattr(chat_module, "run_guarded_chat", _fake_guarded_chat)
    monkeypatch.setattr(chat_module, "ensure_completion_safe", lambda *_: None)
    monkeypatch.setattr(chat_module, "extract_refusal_text", lambda response: response.summary)
    monkeypatch.setattr(chat_module, "TrailService", _DummyTrailService)
    monkeypatch.setattr(chat_module, "get_settings", lambda: SimpleNamespace(intent_tagger_enabled=False))

    payload = ChatSessionRequest(
        messages=[ChatSessionMessage(role="user", content="Tell me about grace")]
    )
    response = api_client.post("/ai/chat", json=payload.model_dump(mode="json"))

    assert response.status_code == 200
    body = response.json()
    assert body["answer"]["summary"] == "Grace abounds"
    assert body["message"]["content"] == "Grace abounds"
    assert recorded_question == ["Tell me about grace"]
    # Session identifier should be a valid UUID string
    UUID(body["session_id"])  # raises ValueError if malformed
