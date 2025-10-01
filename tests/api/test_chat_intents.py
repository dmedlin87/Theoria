from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from theo.services.api.app.ai.rag import RAGAnswer
from theo.services.api.app.core.database import get_session
from theo.services.api.app.intent.tagger import IntentTag
from theo.services.api.app.main import app
from theo.services.api.app.routes.ai.workflows import chat as chat_module


class DummySession:
    def get(self, *_: object, **__: object) -> None:
        return None

    def add(self, *_: object, **__: object) -> None:  # pragma: no cover - interface stub
        return None

    def flush(self) -> None:  # pragma: no cover - interface stub
        return None

    def commit(self) -> None:  # pragma: no cover - interface stub
        return None


class DummyRecorder:
    def __init__(self) -> None:
        self.input_kwargs: dict[str, object] | None = None
        self.finalized: dict[str, object] | None = None

    def __enter__(self) -> "DummyRecorder":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # type: ignore[override]
        return False

    def finalize(
        self,
        *,
        final_md: str | None = None,
        output_payload: object = None,
        status: str = "completed",
    ) -> SimpleNamespace:
        self.finalized = {
            "final_md": final_md,
            "output_payload": output_payload,
            "status": status,
        }
        return SimpleNamespace()


class StubTrailService:
    created: list["StubTrailService"] = []

    def __init__(self, _session: object) -> None:
        self.recorder = DummyRecorder()
        self.__class__.created.append(self)

    def start_trail(self, **kwargs: object) -> DummyRecorder:
        self.recorder.input_kwargs = kwargs
        return self.recorder


@pytest.fixture
def chat_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, "ChatTestContext"]]:
    session = DummySession()

    def override_session() -> Iterator[DummySession]:
        yield session

    app.dependency_overrides[get_session] = override_session

    StubTrailService.created.clear()
    monkeypatch.setattr(chat_module, "TrailService", StubTrailService)
    context = ChatTestContext()

    def _persist(*_, prompt: str | None = None, **kwargs: object) -> SimpleNamespace:
        context.persist_calls.append({"prompt": prompt, "kwargs": kwargs})
        return SimpleNamespace(id="session")

    monkeypatch.setattr(chat_module, "_persist_chat_session", _persist)
    monkeypatch.setattr(chat_module, "ensure_completion_safe", lambda *_: None)
    monkeypatch.setattr(
        chat_module,
        "run_guarded_chat",
        lambda *_, **__: RAGAnswer(summary="response", citations=[]),
    )

    try:
        with TestClient(app) as client:
            yield client, context
    finally:
        app.dependency_overrides.pop(get_session, None)


class ChatTestContext:
    def __init__(self) -> None:
        self.persist_calls: list[dict[str, object]] = []

    def last_trail_service(self) -> StubTrailService:
        return StubTrailService.created[-1]

    def last_persist_call(self) -> dict[str, object]:
        if not self.persist_calls:
            raise AssertionError("No chat sessions persisted")
        return self.persist_calls[-1]


def _chat_payload(message: str) -> dict[str, object]:
    return {
        "messages": [{"role": "user", "content": message}],
        "filters": {},
    }


def test_chat_turn_attaches_intent_tags(
    chat_client: tuple[TestClient, ChatTestContext],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, context = chat_client

    settings = SimpleNamespace(intent_tagger_enabled=True, intent_model_path=Path("dummy.joblib"))
    monkeypatch.setattr(chat_module, "get_settings", lambda: settings)

    tag = IntentTag(intent="sermon_prep", stance="supportive", confidence=0.87)

    class StubTagger:
        def predict(self, message: str) -> IntentTag:
            assert message == "Plan a sermon on hope"
            return tag

    monkeypatch.setattr(chat_module, "get_intent_tagger", lambda _settings: StubTagger())

    response = client.post("/ai/chat", json=_chat_payload("Plan a sermon on hope"))
    assert response.status_code == 200

    payload = response.json()
    assert payload["intent_tags"] == [
        {"intent": "sermon_prep", "stance": "supportive", "confidence": pytest.approx(0.87)}
    ]

    recorder = context.last_trail_service().recorder
    assert recorder.finalized is not None
    assert recorder.finalized["output_payload"]["intent_tags"] == [
        {"intent": "sermon_prep", "stance": "supportive", "confidence": 0.87}
    ]


def test_chat_turn_omits_tags_when_disabled(
    chat_client: tuple[TestClient, ChatTestContext],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, context = chat_client

    settings = SimpleNamespace(intent_tagger_enabled=False, intent_model_path=None)
    monkeypatch.setattr(chat_module, "get_settings", lambda: settings)

    def _should_not_run(_settings: object) -> None:
        raise AssertionError("intent tagger should not be resolved when disabled")

    monkeypatch.setattr(chat_module, "get_intent_tagger", _should_not_run)

    response = client.post("/ai/chat", json=_chat_payload("Tell me about Romans 8"))
    assert response.status_code == 200

    payload = response.json()
    assert "intent_tags" not in payload

    recorder = context.last_trail_service().recorder
    assert recorder.finalized is not None
    assert "intent_tags" not in recorder.finalized["output_payload"]


def test_chat_turn_records_prompt(
    chat_client: tuple[TestClient, ChatTestContext],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, context = chat_client

    settings = SimpleNamespace(intent_tagger_enabled=False, intent_model_path=None)
    monkeypatch.setattr(chat_module, "get_settings", lambda: settings)

    response = client.post(
        "/ai/chat",
        json={
            "messages": [{"role": "user", "content": "Summarize John 1"}],
            "filters": {},
            "prompt": "Summarize John 1",
        },
    )

    assert response.status_code == 200

    persist_call = context.last_persist_call()
    assert persist_call["prompt"] == "Summarize John 1"

    recorder = context.last_trail_service().recorder
    assert recorder.input_kwargs is not None
    stored_payload = recorder.input_kwargs.get("input_payload")
    assert isinstance(stored_payload, dict)
    assert stored_payload.get("prompt") == "Summarize John 1"
