from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from theo.services.api.app.analytics.openalex import OpenAlexClient
from theo.services.api.app.analytics.topics import (
    TopicCluster,
    TopicDigest,
    generate_topic_digest,
    store_topic_digest,
)
from theo.application.facades.database import get_engine
from theo.adapters.persistence.models import Document
from theo.application.ports.events import DomainEvent


def test_topic_digest_deduplicates_document_ids() -> None:
    engine = get_engine()
    with Session(engine) as session:
        doc_id = "dedup-topic-doc"
        topic = "Duplicate Topic"

        document = Document(
            id=doc_id,
            title="Deduplicated Topic Document",
            source_type="test",
            bib_json={"primary_topic": topic, "topics": [topic]},
            topics=[topic],
        )
        session.add(document)
        session.commit()

        digest = generate_topic_digest(
            session, since=datetime.now(UTC) - timedelta(days=1)
        )

        cluster = next((item for item in digest.topics if item.topic == topic), None)
        assert cluster is not None, digest
        assert cluster.new_documents == 1
        assert cluster.document_ids == [doc_id]

        session.delete(document)
        session.commit()


class _FakeOpenAlexClient(OpenAlexClient):
    def __init__(self) -> None:
        self.calls: list[tuple[str | None, str | None]] = []

    def fetch_topics(self, doi: str | None = None, title: str | None = None) -> list[str]:
        self.calls.append((doi, title))
        if doi == "10.1234/example":
            return ["Systematic Theology", "Practical Ministry"]
        return []


def test_topic_digest_enriches_documents_with_openalex_topics() -> None:
    engine = get_engine()
    with Session(engine) as session:
        document = Document(
            id="openalex-topic-doc",
            title="Understanding Systematic Theology",
            doi="10.1234/example",
            source_type="test",
            bib_json={},
        )
        session.add(document)
        session.commit()

        client = _FakeOpenAlexClient()

        digest = generate_topic_digest(
            session,
            since=datetime.now(UTC) - timedelta(days=1),
            openalex_client=client,
        )

        session.refresh(document)

        assert client.calls == [("10.1234/example", "Understanding Systematic Theology")]
        assert document.topics == ["Systematic Theology", "Practical Ministry"]
        assert document.bib_json == {"topics": ["Systematic Theology", "Practical Ministry"]}

        cluster = next(
            (item for item in digest.topics if item.topic == "Systematic Theology"),
            None,
        )
        assert cluster is not None, digest
        assert cluster.new_documents == 1
        assert cluster.document_ids == ["openalex-topic-doc"]

        session.delete(document)
        session.commit()


def test_store_topic_digest_emits_event(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = get_engine()
    events: list[DomainEvent] = []

    class _Publisher:
        def publish(self, event: DomainEvent) -> None:
            events.append(event)

    monkeypatch.setattr(
        "theo.services.api.app.analytics.topics.get_event_publisher",
        lambda settings=None: _Publisher(),
    )

    digest = TopicDigest(
        generated_at=datetime.now(UTC),
        window_start=datetime.now(UTC) - timedelta(days=7),
        topics=[
            TopicCluster(
                topic="Systematic Theology",
                new_documents=2,
                total_documents=5,
                document_ids=["doc-1", "doc-2"],
            )
        ],
    )

    with Session(engine) as session:
        store_topic_digest(session, digest)

    assert len(events) == 1
    message = events[0].to_message()
    assert message["type"] == "theo.topic_digest.generated"
    assert message["payload"]["topic_count"] == 1
    assert message["payload"]["digest"]["topics"][0]["topic"] == "Systematic Theology"
