from __future__ import annotations

from theo.services.api.app.models.search import HybridSearchFilters, HybridSearchRequest
from theo.services.api.app.retriever import hybrid


class _DummyDialect:
    name = "postgresql"


class _DummyBind:
    dialect = _DummyDialect()


class _FallbackSession:
    bind = None


class _PostgresSession:
    bind = _DummyBind()


def test_hybrid_search_uses_fallback_backend(monkeypatch):
    called = {}

    def fake_fallback(session, request):
        called["fallback"] = (session, request)
        return []

    def fake_postgres(session, request):  # pragma: no cover - should not run
        raise AssertionError("postgres backend should not be selected")

    monkeypatch.setattr(hybrid, "_fallback_search", fake_fallback)
    monkeypatch.setattr(hybrid, "_postgres_hybrid_search", fake_postgres)

    request = HybridSearchRequest(k=3)
    session = _FallbackSession()

    assert hybrid.hybrid_search(session, request) == []
    assert "fallback" in called
    assert called["fallback"][0] is session


def test_hybrid_search_selects_postgres_backend(monkeypatch):
    called = {}

    def fake_fallback(session, request):  # pragma: no cover - should not run
        raise AssertionError("fallback backend should not be selected")

    def fake_postgres(session, request):
        called["postgres"] = (session, request)
        return []

    monkeypatch.setattr(hybrid, "_fallback_search", fake_fallback)
    monkeypatch.setattr(hybrid, "_postgres_hybrid_search", fake_postgres)

    request = HybridSearchRequest(query="test", filters=HybridSearchFilters())
    session = _PostgresSession()

    assert hybrid.hybrid_search(session, request) == []
    assert "postgres" in called
    assert called["postgres"][0] is session
