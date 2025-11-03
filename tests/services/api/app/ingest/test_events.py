from __future__ import annotations

from types import SimpleNamespace

import pytest

from theo.infrastructure.api.app.ingest import events


class _StubPassage(SimpleNamespace):
    id: str | None


class _StubDocument(SimpleNamespace):
    id: str
    title: str | None
    collection: str | None
    source_type: str | None


def test_emit_document_persisted_event_builds_payload(monkeypatch: pytest.MonkeyPatch) -> None:
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
