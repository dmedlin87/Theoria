from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pytest

from theo.adapters.graph.neo4j import Neo4jGraphProjector
from theo.application.graph import GraphDocumentProjection


@dataclass
class _FakeGraph:
    documents: dict[str, dict[str, Any]] = field(default_factory=dict)
    verses: dict[str, dict[str, Any]] = field(default_factory=dict)
    concepts: dict[str, dict[str, Any]] = field(default_factory=dict)
    relationships: set[tuple[str, str, str, str, str]] = field(default_factory=set)

    def add_document(self, identifier: str, properties: dict[str, Any]) -> None:
        payload = dict(properties)
        payload.setdefault("id", identifier)
        self.documents[identifier] = payload

    def add_verse(self, identifier: str) -> None:
        self.verses.setdefault(identifier, {"osis": identifier})

    def add_concept(self, name: str) -> None:
        self.concepts.setdefault(name, {"name": name})

    def add_relationship(
        self,
        start_label: str,
        start_id: str,
        rel_type: str,
        end_label: str,
        end_id: str,
    ) -> None:
        self.relationships.add((start_label, start_id, rel_type, end_label, end_id))

    def remove_document(self, identifier: str) -> None:
        self.documents.pop(identifier, None)
        self.relationships = {
            rel
            for rel in self.relationships
            if not (
                (rel[0] == "Document" and rel[1] == identifier)
                or (rel[3] == "Document" and rel[4] == identifier)
            )
        }


class _FakeTransaction:
    def __init__(self, graph: _FakeGraph) -> None:
        self._graph = graph

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> None:
        params = parameters or {}
        if query.strip().startswith("MERGE (d:Document"):
            self._graph.add_document(
                params["document_id"],
                {
                    "title": params.get("title"),
                    "source_type": params.get("source_type"),
                    "topic_domains": params.get("topic_domains"),
                    "theological_tradition": params.get("tradition"),
                },
            )
            return
        if "UNWIND $verses" in query and "MATCH (d:Document" in query:
            doc_id = params["document_id"]
            for verse in params.get("verses", []):
                self._graph.add_verse(verse)
                self._graph.add_relationship("Document", doc_id, "MENTIONS", "Verse", verse)
            return
        if "UNWIND $concepts" in query and "MATCH (d:Document" in query:
            doc_id = params["document_id"]
            for concept in params.get("concepts", []):
                self._graph.add_concept(concept)
                self._graph.add_relationship("Document", doc_id, "DISCUSSES", "Concept", concept)
            return
        if query.strip().startswith("UNWIND $concepts AS concept_name"):
            for concept in params.get("concepts", []):
                self._graph.add_concept(concept)
                for verse in params.get("verses", []):
                    self._graph.add_verse(verse)
                    self._graph.add_relationship("Concept", concept, "RELATES_TO", "Verse", verse)
            return
        stripped = " ".join(query.split())
        if stripped.startswith("MATCH (d:Document {id: $document_id}) DETACH DELETE d"):
            self._graph.remove_document(params["document_id"])
            return
        raise NotImplementedError(query)


class _FakeSession:
    def __init__(self, graph: _FakeGraph) -> None:
        self._graph = graph

    def __enter__(self) -> "_FakeSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def execute_write(self, func: Callable[[Any], Any]) -> Any:
        tx = _FakeTransaction(self._graph)
        return func(tx)

    def close(self) -> None:  # pragma: no cover - interface compatibility
        return None


class _FakeDriver:
    def __init__(self) -> None:
        self.graph = _FakeGraph()

    def session(self, database: str | None = None) -> _FakeSession:  # pragma: no cover - database ignored
        return _FakeSession(self.graph)

    def close(self) -> None:  # pragma: no cover - interface compatibility
        return None


@pytest.fixture()
def fake_projector() -> tuple[Neo4jGraphProjector, _FakeDriver]:
    driver = _FakeDriver()
    projector = Neo4jGraphProjector(driver)
    return projector, driver


def test_project_document_creates_nodes_and_edges(fake_projector) -> None:
    projector, driver = fake_projector
    projection = GraphDocumentProjection(
        document_id="doc-1",
        title="Test Document",
        source_type="text",
        verses=("John.3.16", "John.3.17"),
        concepts=("grace", "salvation"),
        topic_domains=("soteriology",),
        theological_tradition="reformed",
    )

    projector.project_document(projection)

    graph = driver.graph
    assert graph.documents["doc-1"]["title"] == "Test Document"
    assert graph.documents["doc-1"]["topic_domains"] == ["soteriology"]

    assert "John.3.16" in graph.verses
    assert "grace" in graph.concepts
    assert ("Document", "doc-1", "MENTIONS", "Verse", "John.3.16") in graph.relationships
    assert ("Document", "doc-1", "DISCUSSES", "Concept", "grace") in graph.relationships
    assert ("Concept", "salvation", "RELATES_TO", "Verse", "John.3.17") in graph.relationships


def test_remove_document_detaches_relationships(fake_projector) -> None:
    projector, driver = fake_projector
    projection = GraphDocumentProjection(
        document_id="doc-2",
        title="Removable",
        source_type="text",
        verses=("Rom.8.1",),
        concepts=("freedom",),
    )

    projector.project_document(projection)
    projector.remove_document("doc-2")

    graph = driver.graph
    assert "doc-2" not in graph.documents
    assert all(rel[1] != "doc-2" for rel in graph.relationships)
    # Concepts and verses remain available for other documents
    assert "Rom.8.1" in graph.verses
    assert "freedom" in graph.concepts


def test_project_document_deduplicates_relationships(fake_projector) -> None:
    projector, driver = fake_projector
    projection = GraphDocumentProjection(
        document_id="doc-3",
        title="Duplicates",
        verses=("John.3.16", "John.3.16", ""),
        concepts=("love", "love", None),
        topic_domains=("agape", "agape"),
    )

    projector.project_document(projection)

    relationships = driver.graph.relationships
    verse_edges = {rel for rel in relationships if rel[2] == "MENTIONS"}
    concept_edges = {rel for rel in relationships if rel[2] == "DISCUSSES"}

    assert verse_edges == {("Document", "doc-3", "MENTIONS", "Verse", "John.3.16")}
    assert concept_edges == {("Document", "doc-3", "DISCUSSES", "Concept", "love")}
    assert driver.graph.documents["doc-3"]["topic_domains"] == ["agape"]


def test_projector_from_config_uses_supplied_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _StubDriver:
        def __init__(self, uri: str, auth: tuple[str, str] | None, database: str | None) -> None:
            captured["uri"] = uri
            captured["auth"] = auth
            captured["database"] = database

        def session(self, database: str | None = None):  # pragma: no cover - not used
            raise AssertionError("Session should not be created in this test")

    def fake_driver(uri: str, auth=None, **kwargs):  # noqa: ANN001 - mimic GraphDatabase.driver signature
        captured["kwargs"] = kwargs
        return _StubDriver(uri, auth, kwargs.get("database"))

    monkeypatch.setattr("theo.adapters.graph.neo4j.GraphDatabase.driver", fake_driver)

    projector = Neo4jGraphProjector.from_config(
        "neo4j://graph:7687",
        user="reader",
        password="secret",
        database="theoria",
        max_connection_lifetime=30,
    )

    assert isinstance(projector, Neo4jGraphProjector)
    assert captured["uri"] == "neo4j://graph:7687"
    assert captured["auth"] == ("reader", "secret")
    assert captured["kwargs"]["max_connection_lifetime"] == 30
    assert captured["database"] == "theoria"
