from types import SimpleNamespace

import pytest

from theo.application import graph as graph_module
from theo.application.facades import graph


@pytest.fixture(autouse=True)
def clear_graph_projector_cache():
    graph.get_graph_projector.cache_clear()
    yield
    graph.get_graph_projector.cache_clear()


def test_get_graph_projector_returns_null_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(graph_projection_enabled=False)
    monkeypatch.setattr(graph, "get_settings", lambda: settings)

    projector = graph.get_graph_projector()

    assert isinstance(projector, graph_module.NullGraphProjector)


def test_get_graph_projector_warns_when_enabled_without_uri(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    settings = SimpleNamespace(
        graph_projection_enabled=True,
        graph_neo4j_uri=None,
        graph_neo4j_username=None,
        graph_neo4j_password=None,
        graph_neo4j_database=None,
    )
    monkeypatch.setattr(graph, "get_settings", lambda: settings)

    class _SentinelNeo4j:
        @classmethod
        def from_config(cls, *_args, **_kwargs):  # pragma: no cover - should not be called
            raise AssertionError("Neo4jGraphProjector.from_config should not be used without a URI")

    monkeypatch.setattr(graph, "Neo4jGraphProjector", _SentinelNeo4j)

    caplog.set_level("WARNING", logger=graph.logger.name)

    projector = graph.get_graph_projector()

    assert isinstance(projector, graph_module.NullGraphProjector)
    assert "graph_neo4j_uri is not set" in caplog.text


def test_get_graph_projector_initialises_neo4j_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        graph_projection_enabled=True,
        graph_neo4j_uri="bolt://localhost:7687",
        graph_neo4j_username="neo",
        graph_neo4j_password="matrix",
        graph_neo4j_database="neo4j",
    )
    monkeypatch.setattr(graph, "get_settings", lambda: settings)

    sentinel = object()
    calls: list[tuple[str, str | None, str | None, str | None]] = []

    class _FakeNeo4j:
        @classmethod
        def from_config(
            cls,
            uri: str,
            *,
            user: str | None,
            password: str | None,
            database: str | None,
        ) -> object:
            calls.append((uri, user, password, database))
            return sentinel

    monkeypatch.setattr(graph, "Neo4jGraphProjector", _FakeNeo4j)

    projector = graph.get_graph_projector()

    assert projector is sentinel
    assert calls == [("bolt://localhost:7687", "neo", "matrix", "neo4j")]

    cached = graph.get_graph_projector()

    assert cached is sentinel
    assert calls == [("bolt://localhost:7687", "neo", "matrix", "neo4j")]
