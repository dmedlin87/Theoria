"""Workflow orchestration tests for chat and loop control endpoints."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, Iterator

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from theo.application.facades.database import get_session
from theo.infrastructure.api.app.ai.rag import GuardrailError, RAGAnswer
from theo.infrastructure.api.app.main import app
from theo.infrastructure.api.app.models.ai import (
    ChatSessionMessage,
    ChatSessionRequest,
    LoopControlAction,
    ResearchLoopState,
    ResearchLoopStatus,
)
from theo.infrastructure.api.app.models.research_plan import ResearchPlan
from theo.infrastructure.api.app.routes.ai.workflows import chat as chat_module


class _DummySession:
    """Lightweight session stub capturing stored records."""

    def __init__(self) -> None:
        self._records: dict[tuple[object, str], object] = {}

    def get(self, model: object, primary_key: str) -> object | None:
        return self._records.get((model, str(primary_key)))

    def add(self, record: object) -> None:  # noqa: D401 - mimic SQLAlchemy API
        identifier = getattr(record, "id", None)
        if identifier is not None:
            self._records[(type(record), str(identifier))] = record

    def flush(self) -> None:  # noqa: D401 - compatibility shim
        return None

    def commit(self) -> None:  # noqa: D401 - compatibility shim
        return None

    def store(self, model: object, identifier: str, record: object) -> None:
        self._records[(model, str(identifier))] = record


@dataclass
class _RecorderEvent:
    kind: str
    payload: dict[str, Any]


class _StubRecorder:
    def __init__(self) -> None:
        self.trail = SimpleNamespace(id="trail-123", status="running", mode=None)
        self.finalize_calls: list[dict[str, Any]] = []
        self.fail_calls: list[str] = []
        self.events: list[_RecorderEvent] = []

    def __enter__(self) -> "_StubRecorder":
        return self

    def __exit__(self, exc_type, exc, _tb) -> bool:  # type: ignore[override]
        if exc_type is not None:
            message = str(exc) if exc else exc_type.__name__
            self.fail(message)
        return False

    def finalize(self, *, final_md: str | None, output_payload: Any, status: str = "completed") -> None:
        self.trail.status = status
        self.finalize_calls.append(
            {"final_md": final_md, "output_payload": output_payload, "status": status}
        )
        self.events.append(_RecorderEvent("finalize", {"status": status}))

    def fail(self, message: str) -> None:
        self.trail.status = "failed"
        self.fail_calls.append(message)
        self.events.append(_RecorderEvent("fail", {"message": message}))


class _StubTrailService:
    def __init__(self, *_: Any, **__: Any) -> None:
        self.start_calls: list[dict[str, Any]] = []
        self.resume_calls: list[dict[str, Any]] = []
        self.recorder = _StubRecorder()

    @contextmanager
    def start_trail(self, **kwargs: Any) -> Iterator[_StubRecorder]:
        self.start_calls.append(kwargs)
        yield self.recorder

    @contextmanager
    def resume_trail(self, trail_id: str, **kwargs: Any) -> Iterator[_StubRecorder]:
        payload = dict(kwargs)
        payload["trail_id"] = trail_id
        self.resume_calls.append(payload)
        yield self.recorder


class _StubAuditWriter:
    calls: list[dict[str, Any]] = []

    @classmethod
    def from_session(cls, _session: object) -> "_StubAuditWriter":
        return cls()

    def log(self, **kwargs: Any) -> None:  # noqa: D401 - logger protocol stub
        type(self).calls.append(kwargs)


class _StubLoopController:
    def __init__(self) -> None:
        self.initialised: list[dict[str, Any]] = []
        self.applied: list[dict[str, Any]] = []

    def initialise(self, session_id: str, *, question: str) -> None:
        self.initialised.append({"session_id": session_id, "question": question})

    def get_plan(self, session_id: str) -> ResearchPlan:
        return ResearchPlan(session_id=session_id, steps=[])

    def get_state(self, session_id: str) -> ResearchLoopState:
        return ResearchLoopState(session_id=session_id)

    def apply_action(
        self, session_id: str, action: LoopControlAction, *, step_id: str | None = None
    ) -> ResearchLoopState:
        self.applied.append({"session_id": session_id, "action": action, "step_id": step_id})
        return ResearchLoopState(
            session_id=session_id,
            status=ResearchLoopStatus.RUNNING,
            last_action=action.value,
        )


@pytest.fixture()
def client_with_session(application_container_factory: Any) -> Iterator[tuple[TestClient, _DummySession]]:
    session = _DummySession()

    def _override_session() -> Iterator[_DummySession]:
        yield session

    with application_container_factory():
        app.dependency_overrides[get_session] = _override_session  # type: ignore[assignment]
        try:
            with TestClient(app) as client:
                yield client, session
        finally:
            app.dependency_overrides.pop(get_session, None)


def _prepare_chat_payload(content: str) -> ChatSessionRequest:
    return ChatSessionRequest(messages=[ChatSessionMessage(role="user", content=content)])


def test_chat_turn_emits_audit_and_trail_events(
    client_with_session: tuple[TestClient, _DummySession], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _session = client_with_session

    created_services: list[_StubTrailService] = []
    _StubAuditWriter.calls = []

    def _make_trail_service(*args: Any, **kwargs: Any) -> _StubTrailService:
        service = _StubTrailService(*args, **kwargs)
        created_services.append(service)
        return service

    monkeypatch.setattr(chat_module, "TrailService", _make_trail_service)
    monkeypatch.setattr(chat_module, "AuditLogWriter", _StubAuditWriter)
    monkeypatch.setattr(chat_module, "get_settings", lambda: SimpleNamespace(intent_tagger_enabled=False))
    monkeypatch.setattr(chat_module, "ensure_completion_safe", lambda *_: None)
    monkeypatch.setattr(chat_module, "extract_refusal_text", lambda answer: answer.summary)

    controller = _StubLoopController()
    monkeypatch.setattr(chat_module, "_get_loop_controller", lambda _session: controller)

    response_answer = RAGAnswer(summary="Grace abounds", citations=[], model_output="Grace abounds")
    monkeypatch.setattr(
        chat_module,
        "run_guarded_chat",
        lambda *_args, **_kwargs: response_answer,
    )

    payload = _prepare_chat_payload("Tell me about grace")
    response = client.post("/ai/chat", json=payload.model_dump(mode="json"))

    assert response.status_code == 200
    body = response.json()
    assert body["answer"]["summary"] == "Grace abounds"
    assert body["message"]["content"] == "Grace abounds"

    assert controller.initialised and controller.initialised[0]["question"] == "Tell me about grace"

    assert _StubAuditWriter.calls, "Audit log should be recorded for telemetry"
    assert _StubAuditWriter.calls[0]["status"] == "generated"

    assert created_services, "Trail service should be initialised"
    recorder = created_services[0].recorder
    assert recorder.finalize_calls and recorder.finalize_calls[0]["status"] == "completed"
    assert any(event.kind == "finalize" for event in recorder.events)


def test_chat_guardrail_failure_records_refusal(
    client_with_session: tuple[TestClient, _DummySession], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _session = client_with_session

    created_services: list[_StubTrailService] = []

    def _make_trail_service(*args: Any, **kwargs: Any) -> _StubTrailService:
        service = _StubTrailService(*args, **kwargs)
        created_services.append(service)
        return service

    _StubAuditWriter.calls = []
    monkeypatch.setattr(chat_module, "TrailService", _make_trail_service)
    monkeypatch.setattr(chat_module, "AuditLogWriter", _StubAuditWriter)
    monkeypatch.setattr(chat_module, "get_settings", lambda: SimpleNamespace(intent_tagger_enabled=False))
    monkeypatch.setattr(chat_module, "ensure_completion_safe", lambda *_: None)
    monkeypatch.setattr(chat_module, "extract_refusal_text", lambda answer: answer.summary)

    controller = _StubLoopController()
    monkeypatch.setattr(chat_module, "_get_loop_controller", lambda _session: controller)

    def _raise_guardrail(*_args: Any, **_kwargs: Any) -> RAGAnswer:
        raise GuardrailError("Blocked", metadata={"code": "guardrail_violation"})

    monkeypatch.setattr(chat_module, "run_guarded_chat", _raise_guardrail)

    monkeypatch.setattr(
        chat_module,
        "guardrail_http_exception",
        lambda exc, *, session, question, osis, filters: JSONResponse(  # noqa: ARG005
            status_code=422,
            content={"detail": {"type": "guardrail_refusal"}, "error": {"code": "AI_GUARDRAIL_VIOLATION"}},
        ),
    )

    payload = _prepare_chat_payload("Tell me about grace")
    response = client.post("/ai/chat", json=payload.model_dump(mode="json"))

    assert response.status_code == 422
    assert _StubAuditWriter.calls and _StubAuditWriter.calls[0]["status"] == "refused"
    assert created_services, "Trail service should be initialised for guardrail failure"
    recorder = created_services[0].recorder
    assert recorder.fail_calls and recorder.fail_calls[0] == "Blocked"
    assert any(event.kind == "fail" for event in recorder.events)


def test_loop_control_state_transitions(
    client_with_session: tuple[TestClient, _DummySession], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, session = client_with_session

    session_id = "session-123"
    session.store(
        chat_module.ChatSession,
        session_id,
        SimpleNamespace(
            id=session_id,
            stance=None,
            summary=None,
            document_ids=[],
            preferences=None,
            goals=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            last_interaction_at=datetime.now(UTC),
        ),
    )

    class _LoopController(_StubLoopController):
        def apply_action(
            self, session_id: str, action: LoopControlAction, *, step_id: str | None = None
        ) -> ResearchLoopState:
            super().apply_action(session_id, action, step_id=step_id)
            return ResearchLoopState(
                session_id=session_id,
                status=ResearchLoopStatus.PAUSED,
                partial_answer="Paused for review",
                last_action=action.value,
            )

    controller = _LoopController()
    monkeypatch.setattr(chat_module, "_get_loop_controller", lambda _session: controller)

    payload = {"action": LoopControlAction.PAUSE.value}
    response = client.post(f"/ai/chat/{session_id}/loop/control", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["state"]["status"] == ResearchLoopStatus.PAUSED.value
    assert body["partial_answer"] == "Paused for review"
    assert controller.applied and controller.applied[0]["action"] is LoopControlAction.PAUSE

