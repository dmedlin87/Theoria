"""Tests ensuring verse graph exports compose nodes and filters correctly."""

import pytest

try:
    from types import SimpleNamespace

    from theo.infrastructure.api.app.db.verse_graph import (
        CommentarySeedRecord,
        PairSeedRecord,
        VerseSeedRelationships,
    )
    from theo.infrastructure.api.app.models.base import Passage
    from theo.infrastructure.api.app.retriever import graph as graph_module
    from theo.infrastructure.api.app.retriever.graph import get_verse_graph
except ModuleNotFoundError as exc:  # pragma: no cover - dependency missing in CI
    pytest.skip(f"dependency not available: {exc}", allow_module_level=True)
except ImportError as exc:  # pragma: no cover - dependency missing in CI
    pytest.skip(f"dependency not available: {exc}", allow_module_level=True)


def test_get_verse_graph_builds_nodes_edges_and_filters(monkeypatch) -> None:
    passage = Passage(
        id="passage-1",
        document_id="doc-1",
        text="In the beginning was the Word",
        osis_ref="John.1.1",
        page_no=1,
        t_start=0.0,
        t_end=5.0,
        meta={
            "source_type": "sermon",
            "collection": "Advent Series",
            "authors": ["John Doe"],
            "document_title": "Incarnation Homily",
        },
    )
    mention = SimpleNamespace(passage=passage, context_snippet="Snippet text")

    monkeypatch.setattr(
        graph_module,
        "get_mentions_for_osis",
        lambda session, osis, filters: [mention],
    )

    relationships = VerseSeedRelationships(
        contradictions=[
            PairSeedRecord(
                id="ctr-1",
                osis_a="John.1.1",
                osis_b="Gen.1.1",
                summary="Apparent contradiction",
                source="Source A",
                tags=["tension"],
                weight=0.3,
                perspective="skeptical",
            )
        ],
        harmonies=[
            PairSeedRecord(
                id="harm-1",
                osis_a="Gen.1.1",
                osis_b="John.1.1",
                summary="Canonical harmony",
                source="Source B",
                tags=["unity"],
                weight=0.8,
                perspective="apologetic",
            )
        ],
        commentaries=[
            CommentarySeedRecord(
                id="comm-1",
                osis="John.1.1",
                title="Patristic reflection",
                excerpt="A commentary excerpt",
                source="Origen",
                tags=["christology"],
                perspective="neutral",
            )
        ],
    )

    monkeypatch.setattr(
        graph_module,
        "load_seed_relationships",
        lambda session, osis: relationships,
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
        "mention:passage-1",
        "verse:Gen.1.1",
        "commentary:comm-1",
    }

    mention_edge = next(edge for edge in response.edges if edge.kind == "mention")
    assert mention_edge.source == "verse:John.1.1"
    assert mention_edge.target == "mention:passage-1"
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
