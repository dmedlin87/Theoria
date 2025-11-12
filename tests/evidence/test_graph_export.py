"""Tests ensuring verse graph exports compose nodes and filters correctly."""

import pytest

try:
    from theo.infrastructure.api.app.retriever import graph as graph_module
    from theo.infrastructure.api.app.retriever.graph import get_verse_graph
except ModuleNotFoundError as exc:  # pragma: no cover - dependency missing in CI
    pytest.skip(f"dependency not available: {exc}", allow_module_level=True)
except ImportError as exc:  # pragma: no cover - dependency missing in CI
    pytest.skip(f"dependency not available: {exc}", allow_module_level=True)


def test_get_verse_graph_builds_nodes_edges_and_filters(
    monkeypatch, verse_graph_mention, verse_seed_relationships
) -> None:
    monkeypatch.setattr(
        graph_module,
        "get_mentions_for_osis",
        lambda session, osis, filters: [verse_graph_mention],
    )

    monkeypatch.setattr(
        graph_module,
        "load_seed_relationships",
        lambda session, osis: verse_seed_relationships,
    )
    monkeypatch.setattr(
        graph_module,
        "osis_intersects",
        lambda lhs, rhs: lhs.lower() == rhs.lower(),
    )

    response = get_verse_graph(object(), "John.1.1")

    node_ids = {node.id for node in response.nodes}
    assert node_ids >= {
        "verse:John.1.1",
        f"mention:{verse_graph_mention.passage.id}",
        "verse:Gen.1.1",
        "commentary:comm-1",
    }

    mention_edge = next(edge for edge in response.edges if edge.kind == "mention")
    assert mention_edge.source == "verse:John.1.1"
    assert mention_edge.target == f"mention:{verse_graph_mention.passage.id}"
    assert mention_edge.collection == "Advent Series"
    assert mention_edge.authors == ["John Doe"]

    relationship_edges = {
        (edge.kind, edge.id)
        for edge in response.edges
        if edge.kind in {"contradiction", "harmony"}
    }
    assert (
        ("contradiction", "contradiction:ctr-1:Gen.1.1") in relationship_edges
    )
    assert ("harmony", "harmony:harm-1:John.1.1") in relationship_edges

    assert response.filters.perspectives == ["apologetic", "neutral", "skeptical"]
    assert response.filters.source_types == ["sermon"]
