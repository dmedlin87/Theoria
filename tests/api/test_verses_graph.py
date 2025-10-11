from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from theo.services.api.app.main import app
from theo.services.api.app.db.models import (
    CommentaryExcerptSeed,
    ContradictionSeed,
    Document,
    HarmonySeed,
    Passage,
)
from theo.services.api.app.ingest.osis import expand_osis_reference


@pytest.fixture()
def api_client(api_engine) -> TestClient:
    with TestClient(app) as client:
        yield client


def _seed_graph_data(engine) -> None:
    with Session(engine) as session:
        doc_pdf = Document(
            id="doc-pdf",
            title="PDF Sermon",
            source_type="pdf",
            collection="Sermons",
            authors=["Alice"],
        )
        doc_markdown = Document(
            id="doc-md",
            title="Markdown Notes",
            source_type="markdown",
            collection="Notes",
            authors=["Bob"],
        )
        session.add_all([doc_pdf, doc_markdown])
        session.flush()

        passage_pdf = Passage(
            id="passage-pdf",
            document_id=doc_pdf.id,
            text="For God so loved the world",
            osis_ref="John.3.16",
            osis_verse_ids=list(sorted(expand_osis_reference("John.3.16"))),
            page_no=3,
            t_start=12.5,
            t_end=18.0,
        )
        passage_markdown = Passage(
            id="passage-md",
            document_id=doc_markdown.id,
            text="Study notes on John 3:16",
            osis_ref="John.3.16",
            osis_verse_ids=list(sorted(expand_osis_reference("John.3.16"))),
        )
        session.add_all([passage_pdf, passage_markdown])

        contradiction = ContradictionSeed(
            id=str(uuid4()),
            osis_a="John.3.16",
            osis_b="Matthew.5.44",
            summary="Perceived tension between love and enemies",
            source="Skeptic Digest",
            tags=["tension"],
            weight=1.2,
            perspective="skeptical",
        )
        harmony = HarmonySeed(
            id=str(uuid4()),
            osis_a="John.3.16",
            osis_b="Luke.6.27",
            summary="Shared emphasis on love",
            source="Harmony Notes",
            tags=["love"],
            weight=0.8,
            perspective="apologetic",
        )
        commentary = CommentaryExcerptSeed(
            id=str(uuid4()),
            osis="John.3.16",
            title="Ancient Commentary",
            excerpt="Insight into the verse context",
            source="Church Fathers",
            tags=["historical"],
            perspective=None,
        )
        session.add_all([contradiction, harmony, commentary])
        session.commit()


def test_verse_graph_endpoint_combines_mentions_and_seeds(api_client: TestClient, api_engine) -> None:
    _seed_graph_data(api_engine)

    response = api_client.get("/verses/John.3.16/graph")
    assert response.status_code == 200

    payload = response.json()
    assert payload["osis"] == "John.3.16"

    nodes = {node["id"]: node for node in payload["nodes"]}
    edges = payload["edges"]

    assert "verse:John.3.16" in nodes
    mention_nodes = [node for node in nodes.values() if node["kind"] == "mention"]
    assert len(mention_nodes) == 2
    mention_node = next(node for node in mention_nodes if node["id"] == "mention:passage-pdf")
    assert mention_node["data"]["document_id"] == "doc-pdf"

    mention_edges = [edge for edge in edges if edge["kind"] == "mention"]
    assert {edge["source_type"] for edge in mention_edges} == {"pdf", "markdown"}

    contradiction_edge = next(edge for edge in edges if edge["kind"] == "contradiction")
    assert contradiction_edge["perspective"] == "skeptical"
    assert contradiction_edge["related_osis"] == "Matthew.5.44"

    harmony_edge = next(edge for edge in edges if edge["kind"] == "harmony")
    assert harmony_edge["perspective"] == "apologetic"

    commentary_edge = next(edge for edge in edges if edge["kind"] == "commentary")
    assert commentary_edge["perspective"] == "neutral"

    assert sorted(payload["filters"]["perspectives"]) == ["apologetic", "neutral", "skeptical"]
    assert sorted(payload["filters"]["source_types"]) == ["markdown", "pdf"]


def test_verse_graph_respects_source_type_filter(api_client: TestClient, api_engine) -> None:
    _seed_graph_data(api_engine)

    response = api_client.get("/verses/John.3.16/graph", params={"source_type": "pdf"})
    assert response.status_code == 200

    payload = response.json()
    mention_edges = [edge for edge in payload["edges"] if edge["kind"] == "mention"]
    assert len(mention_edges) == 1
    assert mention_edges[0]["source_type"] == "pdf"

    # Seed relationships remain available even when mention filters are active
    assert any(edge["kind"] == "contradiction" for edge in payload["edges"])
    assert any(edge["kind"] == "commentary" for edge in payload["edges"])
