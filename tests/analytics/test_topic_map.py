from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Iterator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from theo.application.facades import settings as settings_module
from theo.application.facades.database import Base
from theo.infrastructure.api.app.analytics.topic_map import TopicMapBuilder
from theo.adapters.persistence.models import (
    AnalyticsTopicMapSnapshot,
    Document,
    Passage,
)
from theo.infrastructure.api.app.workers import tasks


@pytest.fixture()
def sqlite_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    monkeypatch.setenv("EMBEDDING_DIM", "4")
    settings_module.get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{tmp_path / 'topic_map.sqlite'}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        settings_module.get_settings.cache_clear()


def _create_document(
    session: Session,
    *,
    title: str,
    topics: list[str],
    embedding: list[float],
) -> Document:
    document = Document(title=title, topics=topics)
    session.add(document)
    session.flush()
    passage = Passage(
        document_id=document.id,
        text=f"{title} passage",
        raw_text=f"{title} passage",
        tokens=len(title.split()),
        embedding=embedding,
    )
    session.add(passage)
    session.flush()
    return document


def _seed_topic_documents(session: Session) -> dict[str, list[str]]:
    topic_documents: dict[str, set[str]] = defaultdict(set)
    specs = [
        ("Document A", ["Theology", "Ethics"], [1.0, 0.0, 0.0, 0.0]),
        ("Document B", ["Theology", "History"], [0.8, 0.2, 0.0, 0.0]),
        ("Document C", ["History", "Liturgy"], [0.1, 0.9, 0.0, 0.0]),
    ]
    for title, topics, embedding in specs:
        document = _create_document(
            session,
            title=title,
            topics=list(topics),
            embedding=list(embedding),
        )
        for topic in topics:
            topic_documents[topic.lower()].add(document.id)
    session.commit()
    return {key: sorted(values) for key, values in topic_documents.items()}


def _serialise_snapshot(session: Session, scope: str = "global") -> dict[str, object]:
    snapshot = session.scalar(
        select(AnalyticsTopicMapSnapshot).where(AnalyticsTopicMapSnapshot.scope == scope)
    )
    assert snapshot is not None
    node_map = {}
    nodes = []
    for node in snapshot.nodes:
        embedding = tuple(round(component, 6) for component in (node.embedding or []))
        meta = node.meta or {}
        documents = sorted(meta.get("documentIds", []))
        titles = tuple(meta.get("sampleTitles", []))
        record = {
            "key": node.node_key,
            "label": node.label,
            "weight": round(float(node.weight or 0.0), 6),
            "documents": documents,
            "titles": titles,
            "embedding": embedding,
        }
        nodes.append(record)
        node_map[node.id] = node.node_key
    edges = []
    for edge in snapshot.edges:
        meta = edge.meta or {}
        documents = sorted(meta.get("sharedDocuments", []))
        record = {
            "pair": tuple(sorted((node_map[edge.src_node_id], node_map[edge.dst_node_id]))),
            "type": edge.edge_type.value,
            "weight": round(float(edge.weight or 0.0), 6),
            "shared": documents,
            "similarity": round(float(meta.get("similarity", 0.0)), 6),
        }
        edges.append(record)
    nodes.sort(key=lambda item: item["key"])
    edges.sort(key=lambda item: item["pair"])
    return {
        "snapshot_id": snapshot.id,
        "generated_at": snapshot.generated_at,
        "nodes": nodes,
        "edges": edges,
    }


def test_topic_map_builder_idempotent(sqlite_session: Session) -> None:
    topic_map = _seed_topic_documents(sqlite_session)
    builder = TopicMapBuilder(sqlite_session, similarity_threshold=0.3)

    first_snapshot = builder.build()
    sqlite_session.commit()
    serialised_first = _serialise_snapshot(sqlite_session)

    second_snapshot = builder.build()
    sqlite_session.commit()
    serialised_second = _serialise_snapshot(sqlite_session)

    assert first_snapshot.id == second_snapshot.id
    assert serialised_first["nodes"] == serialised_second["nodes"]
    assert serialised_first["edges"] == serialised_second["edges"]
    assert len(serialised_first["nodes"]) == 4
    assert {node["key"] for node in serialised_first["nodes"]} == {
        "theology",
        "ethics",
        "history",
        "liturgy",
    }
    theology_node = next(node for node in serialised_first["nodes"] if node["key"] == "theology")
    assert theology_node["documents"] == topic_map["theology"]
    assert len(serialised_first["edges"]) >= 3


def test_refresh_topic_map_task_generates_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EMBEDDING_DIM", "4")
    settings_module.get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{tmp_path / 'topic_map_task.sqlite'}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with SessionLocal() as session:
        _seed_topic_documents(session)

    monkeypatch.setattr(tasks, "get_engine", lambda: engine)

    try:
        metrics = tasks.refresh_topic_map(scope="global")
        assert metrics["scope"] == "global"
        assert metrics["topic_count"] == 4
        assert metrics["edge_count"] >= 3
        with SessionLocal() as session:
            snapshot = session.scalar(select(AnalyticsTopicMapSnapshot))
            assert snapshot is not None
            assert len(snapshot.nodes) == metrics["topic_count"]
    finally:
        engine.dispose()
        settings_module.get_settings.cache_clear()


def test_topic_map_builder_handles_mismatched_dimensions(sqlite_session: Session) -> None:
    _create_document(
        sqlite_session,
        title="Vector Four",
        topics=["A"],
        embedding=[1.0, 0.0, 0.0, 0.0],
    )
    _create_document(
        sqlite_session,
        title="Vector Three",
        topics=["B"],
        embedding=[0.5, 0.5, 0.5],
    )
    sqlite_session.commit()

    builder = TopicMapBuilder(sqlite_session, similarity_threshold=0.2)

    snapshot = builder.build()

    assert snapshot.meta == {
        "document_count": 2,
        "topic_count": 2,
    }
    assert not snapshot.edges
