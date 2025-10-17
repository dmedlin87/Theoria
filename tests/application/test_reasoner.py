from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from theo.adapters.graph import GraphEdge, GraphNeighborhood, GraphNode
from theo.adapters.persistence.models import (
    Base,
    CaseEdge,
    CaseEdgeKind,
    CaseObject,
    Document,
)
from theo.application.reasoner import NeighborhoodReasoner
from theo.application.reasoner.events import DocumentPersistedEvent


def _build_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


class _StaticAdapter:
    def __init__(self, neighborhood: GraphNeighborhood) -> None:
        self._neighborhood = neighborhood

    def load_neighborhood(self, document_id: str) -> GraphNeighborhood:
        return self._neighborhood


def test_reasoner_assigns_tags_with_mocked_graph() -> None:
    session = _build_session()
    try:
        document = Document(id="doc-1", title="Focus", topics=["Christology"])
        case_object = CaseObject(id="co-1", document_id=document.id, meta={})
        session.add_all([document, case_object])
        session.commit()

        neighborhood = GraphNeighborhood(
            focus_ids=[case_object.id],
            nodes={
                "co-1": GraphNode(
                    id="co-1",
                    document_id=document.id,
                    topics=["Christology"],
                    topic_domains=["Doctrine"],
                    doctrine="Trinitarian",
                    is_focus=True,
                ),
                "co-2": GraphNode(
                    id="co-2",
                    document_id="doc-2",
                    topics=["Christology"],
                    topic_domains=["Doctrine"],
                    doctrine="Trinitarian",
                    is_focus=False,
                ),
            },
            edges=[
                GraphEdge(
                    source="co-1", target="co-2", kind="topic_overlap", weight=0.9
                )
            ],
        )

        reasoner = NeighborhoodReasoner(
            graph_adapter_factory=lambda _session: _StaticAdapter(neighborhood)
        )
        event = DocumentPersistedEvent(
            document_id=document.id,
            passage_ids=["passage-1"],
            passage_count=1,
            topics=["Christology"],
            topic_domains=["Doctrine"],
            theological_tradition="Trinitarian",
            source_type="txt",
        )

        report = reasoner.handle_document_persisted(session, event)
        session.commit()

        assert report.updated_case_objects == [case_object.id]
        refreshed = session.get(CaseObject, case_object.id)
        assert refreshed is not None
        assert "reasoner:topic:Christology" in (refreshed.tags or [])
        reasoner_meta = (refreshed.meta or {}).get("reasoner")
        assert reasoner_meta is not None
        assert reasoner_meta["inferred_tags"]
    finally:
        session.close()
        session.bind.dispose()  # type: ignore[arg-type]


def test_reasoner_end_to_end_with_sql_adapter() -> None:
    session = _build_session()
    try:
        focus_document = Document(
            id="doc-focus",
            title="Focus Document",
            topics=["Spiritual Formation"],
        )
        neighbor_document = Document(
            id="doc-neighbour",
            title="Neighbour Document",
            topics=["Spiritual Formation"],
            theological_tradition="Reformed",
        )
        session.add_all([focus_document, neighbor_document])
        session.flush()

        focus_object = CaseObject(
            id="co-focus",
            document_id=focus_document.id,
            meta={"passage_meta": {"topic_domains": ["Spiritual Formation"]}},
        )
        neighbour_object = CaseObject(
            id="co-neighbour",
            document_id=neighbor_document.id,
            meta={"passage_meta": {"topic_domains": ["Spiritual Formation"]}},
        )
        session.add_all([focus_object, neighbour_object])
        session.flush()

        edge = CaseEdge(
            src_object_id=focus_object.id,
            dst_object_id=neighbour_object.id,
            kind=CaseEdgeKind.TOPIC_OVERLAP,
            weight=0.8,
        )
        session.add(edge)
        session.commit()

        reasoner = NeighborhoodReasoner()
        event = DocumentPersistedEvent(
            document_id=focus_document.id,
            passage_ids=["passage-1"],
            passage_count=1,
            topics=["Spiritual Formation"],
            topic_domains=["Spiritual Formation"],
            theological_tradition=None,
            source_type="txt",
        )

        report = reasoner.handle_document_persisted(session, event)
        session.commit()

        refreshed = session.get(CaseObject, focus_object.id)
        assert refreshed is not None
        tags = refreshed.tags or []
        assert "reasoner:topic_domain:Spiritual Formation" in tags
        assert "reasoner:doctrine:Reformed" in tags
        assert report.updated_case_objects == [focus_object.id]
        assert report.clusters
        cluster = next(iter(report.clusters.values()))
        assert set(cluster.member_ids) == {focus_object.id, neighbour_object.id}
    finally:
        session.close()
        session.bind.dispose()  # type: ignore[arg-type]

