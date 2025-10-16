"""Service layer orchestrating discovery persistence and retrieval."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Iterable, Mapping, Sequence

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from theo.domain.discoveries import (
    AnomalyDiscoveryEngine,
    ConnectionDiscoveryEngine,
    ContradictionDiscoveryEngine,
    CorpusSnapshotSummary,
    DiscoveryType,
    DocumentEmbedding,
    GapDiscoveryEngine,
    PatternDiscoveryEngine,
    TrendDiscoveryEngine,
)

from ..db.models import CorpusSnapshot, Discovery, Document, Passage


def _coerce_topics(raw: object) -> list[str]:
    topics: list[str] = []
    if isinstance(raw, str):
        value = raw.strip()
        if value:
            topics.append(value)
    elif isinstance(raw, Iterable):
        for item in raw:
            if isinstance(item, str):
                value = item.strip()
                if value:
                    topics.append(value)
            elif isinstance(item, Mapping):
                for key in ("label", "name", "topic", "value"):
                    candidate = item.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        topics.append(candidate.strip())
                        break
    return topics


class DiscoveryService:
    """High-level API for working with discovery records."""

    def __init__(
        self,
        session: Session,
        pattern_engine: PatternDiscoveryEngine | None = None,
        contradiction_engine: ContradictionDiscoveryEngine | None = None,
        trend_engine: TrendDiscoveryEngine | None = None,
        anomaly_engine: AnomalyDiscoveryEngine | None = None,
        connection_engine: ConnectionDiscoveryEngine | None = None,
        gap_engine: GapDiscoveryEngine | None = None,
    ):
        self.session = session
        self.pattern_engine = pattern_engine or PatternDiscoveryEngine()
        self.contradiction_engine = contradiction_engine or ContradictionDiscoveryEngine()
        self.trend_engine = trend_engine or TrendDiscoveryEngine()
        self.anomaly_engine = anomaly_engine or AnomalyDiscoveryEngine()
        self.connection_engine = connection_engine or ConnectionDiscoveryEngine()
        self.gap_engine = gap_engine or GapDiscoveryEngine()

    def list(
        self,
        user_id: str,
        *,
        discovery_type: str | None = None,
        viewed: bool | None = None,
    ) -> list[Discovery]:
        stmt = select(Discovery).where(Discovery.user_id == user_id)
        if discovery_type:
            stmt = stmt.where(Discovery.discovery_type == discovery_type)
        if viewed is not None:
            stmt = stmt.where(Discovery.viewed == viewed)
        stmt = stmt.order_by(Discovery.created_at.desc())
        return list(self.session.scalars(stmt))

    def mark_viewed(self, user_id: str, discovery_id: int) -> Discovery:
        discovery = self._get_user_discovery(user_id, discovery_id)
        if not discovery.viewed:
            discovery.viewed = True
            self.session.commit()
        return discovery

    def set_feedback(
        self, user_id: str, discovery_id: int, reaction: str | None
    ) -> Discovery:
        discovery = self._get_user_discovery(user_id, discovery_id)
        discovery.user_reaction = reaction
        self.session.commit()
        return discovery

    def dismiss(self, user_id: str, discovery_id: int) -> None:
        discovery = self._get_user_discovery(user_id, discovery_id)
        discovery.viewed = True
        discovery.user_reaction = "dismissed"
        self.session.commit()

    def refresh_user_discoveries(self, user_id: str) -> list[Discovery]:
        documents = self._load_document_embeddings(user_id)
        
        # Run pattern detection
        pattern_candidates, snapshot = self.pattern_engine.detect(documents)

        # Run contradiction detection
        contradiction_candidates = self.contradiction_engine.detect(documents)

        # Prepare trend analysis using historical snapshots including the new run
        historical_snapshots = self._load_recent_snapshots(
            user_id, limit=self.trend_engine.history_window - 1
        )
        trend_candidates = self.trend_engine.detect([*historical_snapshots, snapshot])

        # Delete old discoveries (patterns, contradictions, and trends)
        # Run anomaly detection
        anomaly_candidates = self.anomaly_engine.detect(documents)

        # Delete old discoveries (both patterns and contradictions)
        self.session.execute(
            delete(Discovery).where(
                Discovery.user_id == user_id,
                Discovery.discovery_type.in_(
                    [
                        DiscoveryType.PATTERN.value,
                        DiscoveryType.CONTRADICTION.value,
                        DiscoveryType.ANOMALY.value,
                    ]
                ),
            )
        )
        # Run connection detection
        connection_candidates = self.connection_engine.detect(documents)

        # Delete old discoveries (patterns, contradictions, and connections)
        # Run gap detection
        gap_candidates = self.gap_engine.detect(documents)

        # Delete old discoveries (patterns, contradictions, and gaps)
        self.session.execute(
            delete(Discovery).where(
                Discovery.user_id == user_id,
                Discovery.discovery_type.in_([
                    DiscoveryType.PATTERN.value,
                    DiscoveryType.CONTRADICTION.value,
                    DiscoveryType.TREND.value,
                    DiscoveryType.CONNECTION.value,
                    DiscoveryType.GAP.value,
                ]),
            )
        )

        persisted: list[Discovery] = []
        
        # Persist pattern discoveries
        for candidate in pattern_candidates:
            record = Discovery(
                user_id=user_id,
                discovery_type=DiscoveryType.PATTERN.value,
                title=candidate.title,
                description=candidate.description,
                confidence=float(candidate.confidence),
                relevance_score=float(candidate.relevance_score),
                viewed=False,
                meta=dict(candidate.metadata),
                created_at=datetime.now(UTC),
            )
            self.session.add(record)
            persisted.append(record)
        
        # Persist contradiction discoveries
        for candidate in contradiction_candidates:
            record = Discovery(
                user_id=user_id,
                discovery_type=DiscoveryType.CONTRADICTION.value,
                title=candidate.title,
                description=candidate.description,
                confidence=float(candidate.confidence),
                relevance_score=float(candidate.relevance_score),
                viewed=False,
                meta={
                    "document_a_id": candidate.document_a_id,
                    "document_b_id": candidate.document_b_id,
                    "document_a_title": candidate.document_a_title,
                    "document_b_title": candidate.document_b_title,
                    "claim_a": candidate.claim_a,
                    "claim_b": candidate.claim_b,
                    "contradiction_type": candidate.contradiction_type,
                    **candidate.metadata,
                },
                created_at=datetime.now(UTC),
            )
            self.session.add(record)
            persisted.append(record)

        # Persist trend discoveries
        for candidate in trend_candidates:
            record = Discovery(
                user_id=user_id,
                discovery_type=DiscoveryType.TREND.value,
        # Persist anomaly discoveries
        for candidate in anomaly_candidates:
            record = Discovery(
                user_id=user_id,
                discovery_type=DiscoveryType.ANOMALY.value,
        # Persist connection discoveries
        for candidate in connection_candidates:
            record = Discovery(
                user_id=user_id,
                discovery_type=DiscoveryType.CONNECTION.value,
        # Persist gap discoveries
        for candidate in gap_candidates:
            metadata = {
                "reference_topic": candidate.reference_topic,
                "missing_keywords": list(candidate.missing_keywords),
                "shared_keywords": list(candidate.shared_keywords),
                "related_documents": list(candidate.related_documents),
            }
            metadata.update(dict(candidate.metadata))
            record = Discovery(
                user_id=user_id,
                discovery_type=DiscoveryType.GAP.value,
                title=candidate.title,
                description=candidate.description,
                confidence=float(candidate.confidence),
                relevance_score=float(candidate.relevance_score),
                viewed=False,
                meta=dict(candidate.metadata),
                created_at=datetime.now(UTC),
            )
            self.session.add(record)
            persisted.append(record)

        snapshot_row = CorpusSnapshot(
            user_id=user_id,
            snapshot_date=snapshot.snapshot_date,
            document_count=snapshot.document_count,
            verse_coverage=dict(snapshot.verse_coverage),
            dominant_themes=dict(snapshot.dominant_themes),
            meta=dict(snapshot.metadata),
        )
        self.session.add(snapshot_row)
        self.session.commit()
        return persisted

    def _get_user_discovery(self, user_id: str, discovery_id: int) -> Discovery:
        stmt = select(Discovery).where(
            Discovery.id == discovery_id,
            Discovery.user_id == user_id,
        )
        discovery = self.session.scalars(stmt).one_or_none()
        if discovery is None:
            raise LookupError(f"Discovery {discovery_id} not found for user {user_id}")
        return discovery

    def _load_document_embeddings(self, user_id: str) -> list[DocumentEmbedding]:
        stmt = select(
            Document.id,
            Document.title,
            Document.abstract,
            Document.topics,
        ).where(Document.collection == user_id)
        rows = self.session.execute(stmt).all()
        documents: dict[str, dict[str, object]] = {}
        for row in rows:
            doc_id: str = row.id
            documents[doc_id] = {
                "title": row.title or "Untitled Document",
                "abstract": row.abstract,
                "topics": _coerce_topics(row.topics or []),
            }
        if not documents:
            return []

        passage_stmt = select(
            Passage.document_id,
            Passage.embedding,
            Passage.osis_verse_ids,
        ).where(Passage.document_id.in_(documents.keys()))
        embedding_map: dict[str, list[Sequence[float]]] = defaultdict(list)
        verse_map: dict[str, set[int]] = defaultdict(set)
        for record in self.session.execute(passage_stmt):
            embedding = record.embedding
            if embedding is None:
                continue
            embedding_map[record.document_id].append(embedding)
            if record.osis_verse_ids:
                verse_ids = record.osis_verse_ids
                if isinstance(verse_ids, Iterable):
                    for verse in verse_ids:
                        if isinstance(verse, int):
                            verse_map[record.document_id].add(verse)
        result: list[DocumentEmbedding] = []
        for doc_id, meta in documents.items():
            vectors = embedding_map.get(doc_id)
            if not vectors:
                continue
            averaged = self._average_vectors(vectors)
            if not averaged:
                continue
            verse_ids = sorted(verse_map.get(doc_id, set()))
            metadata = {
                "keywords": meta["topics"],
                "documentId": doc_id,
            }
            result.append(
                DocumentEmbedding(
                    document_id=doc_id,
                    title=str(meta["title"]),
                    abstract=meta.get("abstract") if isinstance(meta.get("abstract"), str) else None,
                    topics=list(meta["topics"]),
                    verse_ids=verse_ids,
                    embedding=averaged,
                    metadata=metadata,
                )
            )
        return result

    def _load_recent_snapshots(
        self, user_id: str, *, limit: int | None = None
    ) -> list[CorpusSnapshotSummary]:
        stmt = (
            select(CorpusSnapshot)
            .where(CorpusSnapshot.user_id == user_id)
            .order_by(CorpusSnapshot.snapshot_date.desc())
        )
        if limit is not None and limit > 0:
            stmt = stmt.limit(limit)
        rows = list(self.session.scalars(stmt))
        snapshots = [
            CorpusSnapshotSummary(
                snapshot_date=row.snapshot_date,
                document_count=row.document_count,
                verse_coverage=row.verse_coverage or {},
                dominant_themes=row.dominant_themes or {},
                metadata=row.meta or {},
            )
            for row in rows
        ]
        snapshots.reverse()
        return snapshots

    @staticmethod
    def _average_vectors(vectors: Sequence[Sequence[float]]) -> list[float]:
        array = np.array(vectors, dtype=float)
        if not np.isfinite(array).all():
            array = array[np.isfinite(array).all(axis=1)]
        if len(array) == 0:
            return []
        return array.mean(axis=0).tolist()


__all__ = ["DiscoveryService"]
