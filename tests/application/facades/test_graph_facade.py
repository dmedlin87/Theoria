import types

import pytest

from theo.application.facades import graph as graph_facade
from theo.application.graph import NullGraphProjector


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    graph_facade.get_graph_projector.cache_clear()
    try:
        yield
    finally:
        graph_facade.get_graph_projector.cache_clear()


def test_get_graph_projector_returns_noop_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        graph_facade,
        "get_settings",
        lambda: types.SimpleNamespace(graph_projection_enabled=False),
    )

    projector = graph_facade.get_graph_projector()

    assert isinstance(projector, NullGraphProjector)


def test_get_graph_projector_requires_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        graph_facade,
        "get_settings",
        lambda: types.SimpleNamespace(graph_projection_enabled=True, graph_neo4j_uri=None),
    )

    projector = graph_facade.get_graph_projector()

    assert isinstance(projector, NullGraphProjector)


def test_get_graph_projector_uses_neo4j_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = types.SimpleNamespace(
        graph_projection_enabled=True,
        graph_neo4j_uri="bolt://localhost",
        graph_neo4j_username="neo4j",
        graph_neo4j_password="secret",
        graph_neo4j_database="neo4j",
    )
    monkeypatch.setattr(graph_facade, "get_settings", lambda: settings)

    class _FakeProjector:
        def __init__(self, uri: str, user: str | None, password: str | None, database: str | None) -> None:
            self.uri = uri
            self.user = user
            self.password = password
            self.database = database

        @classmethod
        def from_config(
            cls,
            uri: str,
            *,
            user: str | None,
            password: str | None,
            database: str | None,
        ) -> "_FakeProjector":
            return cls(uri, user, password, database)

    monkeypatch.setattr(graph_facade, "Neo4jGraphProjector", _FakeProjector)

    projector = graph_facade.get_graph_projector()

    assert isinstance(projector, _FakeProjector)
    assert projector.uri == "bolt://localhost"
    assert projector.user == "neo4j"
    assert projector.database == "neo4j"
