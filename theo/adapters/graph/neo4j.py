"""Neo4j adapter implementing the graph projection port."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from neo4j import Driver as _Driver, GraphDatabase

from theo.application.graph import GraphDocumentProjection, GraphProjector


@dataclass(slots=True)
class _SessionFactory:
    """Lightweight wrapper to allow duck-typed test doubles."""

    driver: _Driver
    database: str | None = None

    def __call__(self) -> Any:
        return self.driver.session(database=self.database)


class Neo4jGraphProjector(GraphProjector):
    """Project documents, concepts, and verses into a Neo4j graph."""

    def __init__(self, driver: _Driver, *, database: str | None = None) -> None:
        self._factory = _SessionFactory(driver=driver, database=database)
        self._driver = driver
        self._database = database

    @classmethod
    def from_config(
        cls,
        uri: str,
        *,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
        **driver_kwargs: Any,
    ) -> "Neo4jGraphProjector":
        """Create a projector using connection details from configuration."""

        auth: tuple[str, str] | None
        if user is None:
            auth = None
        else:
            auth = (user, password or "")
        driver = GraphDatabase.driver(uri, auth=auth, **driver_kwargs)
        return cls(driver, database=database)

    def close(self) -> None:
        """Close the underlying Neo4j driver."""

        self._driver.close()

    # ------------------------------------------------------------------
    # GraphProjector API
    # ------------------------------------------------------------------
    def project_document(self, projection: GraphDocumentProjection) -> None:
        verses = _normalise_sequence(projection.verses)
        concepts = _normalise_sequence(projection.concepts)
        topic_domains = list(_normalise_sequence(projection.topic_domains))
        metadata = {
            "document_id": projection.document_id,
            "title": projection.title,
            "source_type": projection.source_type,
            "topic_domains": topic_domains if topic_domains else None,
            "tradition": projection.theological_tradition,
            "verses": verses,
            "concepts": concepts,
        }

        def _write(tx) -> None:
            tx.run(
                """
                MERGE (d:Document {id: $document_id})
                SET d.title = $title,
                    d.source_type = $source_type,
                    d.topic_domains = $topic_domains,
                    d.theological_tradition = $tradition,
                    d.updated_at = datetime()
                """,
                metadata,
            )
            if verses:
                tx.run(
                    """
                    MATCH (d:Document {id: $document_id})
                    UNWIND $verses AS verse_id
                    MERGE (v:Verse {osis: verse_id})
                    MERGE (d)-[:MENTIONS]->(v)
                    """,
                    metadata,
                )
            if concepts:
                tx.run(
                    """
                    MATCH (d:Document {id: $document_id})
                    UNWIND $concepts AS concept_name
                    MERGE (c:Concept {name: concept_name})
                    MERGE (d)-[:DISCUSSES]->(c)
                    """,
                    metadata,
                )
            if verses and concepts:
                tx.run(
                    """
                    UNWIND $concepts AS concept_name
                    UNWIND $verses AS verse_id
                    MERGE (c:Concept {name: concept_name})
                    MERGE (v:Verse {osis: verse_id})
                    MERGE (c)-[:RELATES_TO]->(v)
                    """,
                    metadata,
                )

        self._execute_write(_write)

    def remove_document(self, document_id: str) -> None:
        def _write(tx) -> None:
            tx.run(
                """
                MATCH (d:Document {id: $document_id})
                DETACH DELETE d
                """,
                {"document_id": document_id},
            )

        self._execute_write(_write)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _execute_write(self, func: Callable[[Any], Any]) -> Any:
        with self._factory() as session:
            return session.execute_write(func)


def _normalise_sequence(values: Iterable[str | None] | None) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    if not values:
        return ordered
    for value in values:
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


__all__ = ["Neo4jGraphProjector"]
