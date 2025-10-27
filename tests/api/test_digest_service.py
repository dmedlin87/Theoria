from __future__ import annotations

from datetime import UTC, datetime, timedelta

from theo.infrastructure.api.app.ai import digest_service as digest_service_module
from theo.infrastructure.api.app.ai.digest_service import DigestService
from theo.infrastructure.api.app.analytics.topics import TopicCluster, TopicDigest


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

    from theo.infrastructure.api.app.routes import ai as ai_module

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


def test_ensure_latest_generates_when_cache_missing(monkeypatch):
    ttl = timedelta(minutes=45)
    service = DigestService(session=object(), ttl=ttl)
    regenerated = _build_digest(generated_at=datetime.now(UTC))
    calls: list[str] = []

    monkeypatch.setattr(
        digest_service_module, "load_topic_digest", lambda session: None
    )

    from theo.infrastructure.api.app.routes import ai as ai_module

    def _generate(session):
        calls.append("generate")
        return regenerated

    def _upsert(session, digest):
        calls.append("upsert")
        assert digest is regenerated

    def _store(session, digest):
        calls.append("store")
        assert digest is regenerated

    monkeypatch.setattr(ai_module, "generate_topic_digest", _generate)
    monkeypatch.setattr(ai_module, "upsert_digest_document", _upsert)
    monkeypatch.setattr(ai_module, "store_topic_digest", _store)

    result = service.ensure_latest()

    assert result is regenerated
    assert calls == ["generate", "upsert", "store"]


def test_refresh_generates_with_requested_lookback(monkeypatch):
    fixed_now = datetime(2024, 5, 1, 12, 0, tzinfo=UTC)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz is UTC
            return fixed_now

    monkeypatch.setattr(digest_service_module, "datetime", _FrozenDatetime)

    ttl = timedelta(hours=6)
    service = DigestService(session=object(), ttl=ttl)
    regenerated = _build_digest(generated_at=fixed_now)
    captured: dict[str, object] = {}

    from theo.infrastructure.api.app.routes import ai as ai_module

    def _generate(session, since):
        captured["since"] = since
        return regenerated

    def _upsert(session, digest):
        captured["upsert"] = digest

    def _store(session, digest):
        captured["store"] = digest

    monkeypatch.setattr(ai_module, "generate_topic_digest", _generate)
    monkeypatch.setattr(ai_module, "upsert_digest_document", _upsert)
    monkeypatch.setattr(ai_module, "store_topic_digest", _store)

    result = service.refresh(hours=12)

    assert result is regenerated
    assert captured["since"] == fixed_now - timedelta(hours=12)
    assert captured["upsert"] is regenerated
    assert captured["store"] is regenerated
