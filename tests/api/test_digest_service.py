from __future__ import annotations

from datetime import UTC, datetime, timedelta

from theo.services.api.app.ai import digest_service as digest_service_module
from theo.services.api.app.ai.digest_service import DigestService
from theo.services.api.app.analytics.topics import TopicCluster, TopicDigest


def _build_digest(*, generated_at: datetime) -> TopicDigest:
    return TopicDigest(
        generated_at=generated_at,
        window_start=generated_at - timedelta(hours=1),
        topics=[
            TopicCluster(
                topic="Topic",
                new_documents=1,
                total_documents=1,
                document_ids=["doc-1"],
            )
        ],
    )


def test_topic_cluster_serialization():
    cluster = TopicCluster(
        topic="Example",
        new_documents=3,
        total_documents=10,
        document_ids=["doc-a", "doc-b", "doc-c"],
    )

    payload = cluster.model_dump()

    assert payload == {
        "topic": "Example",
        "new_documents": 3,
        "total_documents": 10,
        "document_ids": ["doc-a", "doc-b", "doc-c"],
    }
    assert "summary" not in payload


def test_ensure_latest_returns_cached_when_within_ttl(monkeypatch):
    ttl = timedelta(hours=2)
    service = DigestService(session=object(), ttl=ttl)
    cached = _build_digest(generated_at=datetime.now(UTC) - timedelta(minutes=5))

    monkeypatch.setattr(
        digest_service_module, "load_topic_digest", lambda session: cached
    )

    result = service.ensure_latest()

    assert result is cached


def test_ensure_latest_regenerates_when_expired(monkeypatch):
    ttl = timedelta(minutes=30)
    service = DigestService(session=object(), ttl=ttl)
    expired = _build_digest(generated_at=datetime.now(UTC) - timedelta(hours=2))
    refreshed = _build_digest(generated_at=datetime.now(UTC))
    calls: list[str] = []

    monkeypatch.setattr(
        digest_service_module, "load_topic_digest", lambda session: expired
    )

    from theo.services.api.app.routes import ai as ai_module

    def _generate(session):
        calls.append("generate")
        return refreshed

    def _upsert(session, digest):
        calls.append("upsert")
        assert digest is refreshed

    def _store(session, digest):
        calls.append("store")
        assert digest is refreshed

    monkeypatch.setattr(ai_module, "generate_topic_digest", _generate)
    monkeypatch.setattr(ai_module, "upsert_digest_document", _upsert)
    monkeypatch.setattr(ai_module, "store_topic_digest", _store)

    result = service.ensure_latest()

    assert result is refreshed
    assert calls == ["generate", "upsert", "store"]
