from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from theo.services.api.app.ingest import events


class _StubPassage(SimpleNamespace):
    id: str | None


class _StubDocument(SimpleNamespace):
    id: str
    title: str | None
    collection: str | None
    source_type: str | None


def test_emit_document_persisted_event_builds_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    dispatched: dict[str, dict[str, object]] = {}

    def _capture(payload: dict[str, object]) -> None:
        dispatched["payload"] = payload

    monkeypatch.setattr(events, "_dispatch_neighborhood_event", _capture)

    document = _StubDocument(id=7, title="Study", collection="library", source_type="sermon")
    passages = [_StubPassage(id="p-1"), _StubPassage(id=None)]

    event = events.emit_document_persisted_event(
        document=document,
        passages=passages,
        topics=["Grace", "", "grace"],
        topic_domains=["Ethics", "ETHICS"],
        theological_tradition="Catholic",
        source_type=None,
        metadata={"extra": "value"},
    )

    assert event.document_id == "7"
    assert event.passage_ids == ["p-1"]
    assert event.passage_count == 1
    assert event.topics == ["Grace"]
    assert event.topic_domains == ["Ethics"]
    assert event.theological_tradition == "Catholic"
    assert event.source_type == "sermon"
    assert event.metadata["title"] == "Study"
    assert event.metadata["collection"] == "library"
    assert event.metadata["extra"] == "value"

    assert dispatched["payload"] == event.to_payload()


def test_dispatch_neighborhood_event_uses_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, dict[str, object]] = {}

    class _Task:
        def delay(self, payload: dict[str, object]) -> None:  # noqa: D401 - stub
            called["payload"] = payload

    module_name = "theo.services.api.app.workers.tasks"
    monkeypatch.setitem(sys.modules, module_name, SimpleNamespace(update_neighborhood_analytics=_Task()))

    events._dispatch_neighborhood_event({"document_id": "d-1"})

    assert called["payload"] == {"document_id": "d-1"}


def test_dispatch_neighborhood_event_calls_function_when_delay_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads: list[dict[str, object]] = []

    def _call(payload: dict[str, object]) -> None:
        payloads.append(payload)

    module_name = "theo.services.api.app.workers.tasks"
    monkeypatch.setitem(sys.modules, module_name, SimpleNamespace(update_neighborhood_analytics=_call))

    events._dispatch_neighborhood_event({"k": 1})

    assert payloads == [{"k": 1}]


def test_dispatch_neighborhood_event_logs_exceptions(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    class _FailingTask:
        def delay(self, payload: dict[str, object]) -> None:  # noqa: D401 - stub
            raise RuntimeError("boom")

    module_name = "theo.services.api.app.workers.tasks"
    monkeypatch.setitem(sys.modules, module_name, SimpleNamespace(update_neighborhood_analytics=_FailingTask()))

    with caplog.at_level("ERROR", logger=events.LOGGER.name):
        events._dispatch_neighborhood_event({"document_id": "d-2"})

    assert "Failed to dispatch neighborhood analytics task" in caplog.text
