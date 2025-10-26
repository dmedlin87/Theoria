from datetime import UTC, datetime

import pytest

from theo.application.reasoner.events import DocumentPersistedEvent


def test_document_persisted_event_to_payload_round_trip() -> None:
    event = DocumentPersistedEvent(
        document_id="doc-1",
        passage_ids=["a", "b"],
        passage_count=2,
        topics=["Grace", "grace"],
        topic_domains=["Doctrine"],
        theological_tradition="Reformed",
        source_type="pdf",
        emitted_at=datetime(2024, 5, 1, tzinfo=UTC).isoformat(timespec="seconds"),
        metadata={"ingested_by": "tests"},
    )

    payload = event.to_payload()
    reconstructed = DocumentPersistedEvent.from_payload(payload)

    assert reconstructed.document_id == "doc-1"
    assert reconstructed.passage_ids == ["a", "b"]
    assert reconstructed.passage_count == 2
    assert reconstructed.topics == ["Grace"]
    assert reconstructed.metadata == {"ingested_by": "tests"}


def test_document_persisted_event_from_payload_normalises_values() -> None:
    payload = {
        "document_id": "doc-1",
        "passage_ids": ["a", None, "A"],
        "topics": ["  Faith  ", "faith"],
        "topic_domains": [" Theology ", ""],
        "passage_count": None,
        "theological_tradition": "  Anglican  ",
        "source_type": "  web  ",
        "metadata": {"attempt": 1},
    }

    event = DocumentPersistedEvent.from_payload(payload)

    assert event.passage_ids == ["a"]
    assert event.passage_count == 1
    assert event.topics == ["Faith"]
    assert event.topic_domains == ["Theology"]
    assert event.theological_tradition == "Anglican"
    assert event.source_type == "web"


def test_document_persisted_event_requires_document_id() -> None:
    with pytest.raises(ValueError):
        DocumentPersistedEvent.from_payload({"document_id": ""})
