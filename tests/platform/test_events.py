from __future__ import annotations

import sys
from types import ModuleType

import pytest

from theo.infrastructure.api.app import events as events_module


def _install_worker_tasks(monkeypatch: pytest.MonkeyPatch, handler: object) -> None:
    package_name = "theo.infrastructure.api.app.workers"
    tasks_name = f"{package_name}.tasks"

    workers_pkg = ModuleType(package_name)
    tasks_module = ModuleType(tasks_name)
    setattr(tasks_module, "on_case_object_upsert", handler)
    setattr(workers_pkg, "tasks", tasks_module)

    monkeypatch.setitem(sys.modules, package_name, workers_pkg)
    monkeypatch.setitem(sys.modules, tasks_name, tasks_module)


def test_notify_document_ingested_records_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def _get_embedding_service():
        calls.setdefault("embedding", 0)
        calls["embedding"] = calls["embedding"] + 1  # type: ignore[operator]

    def _log_workflow_event(event: str, *, workflow: str, **context: object) -> None:
        calls["event"] = event
        calls["workflow"] = workflow
        calls["context"] = context

    monkeypatch.setattr(events_module, "get_embedding_service", _get_embedding_service)
    monkeypatch.setattr(events_module, "log_workflow_event", _log_workflow_event)

    events_module.notify_document_ingested(
        document_id="doc-1",
        workflow="text",
        passage_ids=("p1", "p2"),
        case_object_ids=["c1"],
        metadata={"source": "test"},
    )

    assert calls["embedding"] == 1
    assert calls["event"] == "ingest.document.persisted"
    assert calls["workflow"] == "text"
    context = calls["context"]
    assert context["document_id"] == "doc-1"
    assert context["passage_count"] == 2
    assert context["case_object_count"] == 1
    assert context["metadata"] == {"source": "test"}


def test_notify_case_objects_upserted_uses_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    class Handler:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str | None]] = []

        def delay(self, case_object_id: str, *, document_id: str | None = None) -> None:
            self.calls.append((case_object_id, document_id))

    handler = Handler()
    _install_worker_tasks(monkeypatch, handler)

    events_module.notify_case_objects_upserted(["a", "a", "b "], document_id="doc-42")

    assert handler.calls == [("a", "doc-42"), ("b", "doc-42")]


def test_notify_case_objects_upserted_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    class LegacyHandler:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str | None]] = []

        def delay(self, case_object_id: str) -> None:  # type: ignore[override]
            self.calls.append((case_object_id, None))

    handler = LegacyHandler()
    _install_worker_tasks(monkeypatch, handler)

    events_module.notify_case_objects_upserted(["x"], document_id="ignored")

    assert handler.calls == [("x", None)]

