"""Graph aggregation utilities for verse relationships."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..db.verse_graph import (
    CommentarySeedRecord,
    PairSeedRecord,
    load_seed_relationships,
)
from ..ingest.osis import osis_intersects
from ..models.base import Passage as PassageSchema
from ..models.verses import (
    VerseGraphEdge,
    VerseGraphFilters,
    VerseGraphNode,
    VerseGraphResponse,
    VerseMentionsFilters,
)
from .verses import get_mentions_for_osis


@dataclass(slots=True)
class _NodeBuilder:
    nodes: dict[str, VerseGraphNode]

    def ensure_node(self, node: VerseGraphNode) -> VerseGraphNode:
        existing = self.nodes.get(node.id)
        if existing is not None:
            return existing
        self.nodes[node.id] = node
        return node


def _build_mention_node(
    mention_passage: PassageSchema,
    context_snippet: str,
) -> VerseGraphNode:
    meta = mention_passage.meta or {}
    authors = meta.get("authors")
    if isinstance(authors, list):
        author_list = [str(author) for author in authors if author]
    else:
        author_list = None

    node_data = {
        "document_id": mention_passage.document_id,
        "passage_id": mention_passage.id,
        "page_no": mention_passage.page_no,
        "t_start": mention_passage.t_start,
        "t_end": mention_passage.t_end,
        "context_snippet": context_snippet,
        "source_type": meta.get("source_type"),
        "collection": meta.get("collection"),
        "authors": author_list,
        "document_title": meta.get("document_title"),
    }

    label = str(meta.get("document_title") or "Untitled document")

    return VerseGraphNode(
        id=f"mention:{mention_passage.id}",
        label=label,
        kind="mention",
        osis=None,
        data=node_data,
    )


def _build_related_verse_node(osis: str) -> VerseGraphNode:
    return VerseGraphNode(
        id=f"verse:{osis}",
        label=osis,
        kind="verse",
        osis=osis,
        data=None,
    )


def _build_commentary_node(seed: CommentarySeedRecord) -> VerseGraphNode:
    label = seed.title or seed.source or "Commentary excerpt"
    return VerseGraphNode(
        id=f"commentary:{seed.id}",
        label=label,
        kind="commentary",
        osis=seed.osis,
        data={
            "excerpt": seed.excerpt,
            "source": seed.source,
            "perspective": seed.perspective,
            "tags": seed.tags,
        },
    )


def _build_pair_edge(
    base_node_id: str,
    other_node_id: str,
    seed: PairSeedRecord,
    relation: str,
    *,
    related_osis: str,
) -> VerseGraphEdge:
    return VerseGraphEdge(
        id=f"{relation}:{seed.id}:{related_osis}",
        source=base_node_id,
        target=other_node_id,
        kind=relation,
        summary=seed.summary,
        perspective=seed.perspective,
        tags=seed.tags,
        weight=seed.weight,
        source_type=None,
        collection=None,
        authors=None,
        seed_id=seed.id,
        related_osis=related_osis,
        source_label=seed.source,
    )


def get_verse_graph(
    session: Session,
    osis: str,
    filters: VerseMentionsFilters | None = None,
) -> VerseGraphResponse:
    """Return a graph-centric view of mentions and seed relationships."""

    base_node = VerseGraphNode(
        id=f"verse:{osis}",
        label=osis,
        kind="verse",
        osis=osis,
        data=None,
    )

    node_builder = _NodeBuilder(nodes={base_node.id: base_node})
    edges: list[VerseGraphEdge] = []
    perspectives: set[str] = set()
    source_types: set[str] = set()

    mentions = get_mentions_for_osis(session, osis, filters)
    for mention in mentions:
        passage = mention.passage
        node = _build_mention_node(passage, mention.context_snippet)
        node_builder.ensure_node(node)

        meta = passage.meta or {}
        source_type = str(meta.get("source_type")) if meta.get("source_type") else None
        collection = str(meta.get("collection")) if meta.get("collection") else None
        authors = meta.get("authors")
        author_list = [str(author) for author in authors] if isinstance(authors, list) else None

        if source_type:
            source_types.add(source_type)

        edges.append(
            VerseGraphEdge(
                id=f"mention:{passage.id}",
                source=base_node.id,
                target=node.id,
                kind="mention",
                summary=mention.context_snippet,
                perspective=None,
                tags=None,
                weight=None,
                source_type=source_type,
                collection=collection,
                authors=author_list,
                seed_id=None,
                related_osis=None,
                source_label=meta.get("document_title"),
            )
        )

    seed_relationships = load_seed_relationships(session, osis)

    def _ensure_pair_edge(seed: PairSeedRecord, relation: str) -> None:
        candidates: set[str] = set()
        if osis_intersects(seed.osis_a, osis) or osis_intersects(osis, seed.osis_a):
            candidates.add(seed.osis_b)
        if osis_intersects(seed.osis_b, osis) or osis_intersects(osis, seed.osis_b):
            candidates.add(seed.osis_a)

        if not candidates:
            if seed.osis_a.lower() == osis.lower():
                candidates.add(seed.osis_b)
            elif seed.osis_b.lower() == osis.lower():
                candidates.add(seed.osis_a)

        for candidate in candidates:
            if candidate.lower() == osis.lower():
                continue
            other_node = node_builder.ensure_node(_build_related_verse_node(candidate))
            perspectives.add(seed.perspective)
            edges.append(
                _build_pair_edge(
                    base_node_id=base_node.id,
                    other_node_id=other_node.id,
                    seed=seed,
                    relation=relation,
                    related_osis=candidate,
                )
            )

    for contradiction in seed_relationships.contradictions:
        _ensure_pair_edge(contradiction, "contradiction")

    for harmony in seed_relationships.harmonies:
        _ensure_pair_edge(harmony, "harmony")

    for commentary in seed_relationships.commentaries:
        perspectives.add(commentary.perspective)
        node = node_builder.ensure_node(_build_commentary_node(commentary))
        edges.append(
            VerseGraphEdge(
                id=f"commentary:{commentary.id}",
                source=base_node.id,
                target=node.id,
                kind="commentary",
                summary=commentary.excerpt,
                perspective=commentary.perspective,
                tags=commentary.tags,
                weight=None,
                source_type=None,
                collection=None,
                authors=None,
                seed_id=commentary.id,
                related_osis=commentary.osis,
                source_label=commentary.source,
            )
        )

    filters_payload = VerseGraphFilters(
        perspectives=sorted(perspectives),
        source_types=sorted(source_types),
    )

    return VerseGraphResponse(
        osis=osis,
        nodes=list(node_builder.nodes.values()),
        edges=edges,
        filters=filters_payload,
    )
