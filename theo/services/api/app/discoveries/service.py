"""Service layer orchestrating discovery persistence and retrieval."""

from __future__ import annotations

from datetime import UTC, datetime

from theo.application.dtos import CorpusSnapshotDTO, DiscoveryDTO, DiscoveryListFilters
from theo.application.repositories import DiscoveryRepository, DocumentRepository
from theo.domain.discoveries import (
    AnomalyDiscoveryEngine,
    ConnectionDiscoveryEngine,
    ContradictionDiscoveryEngine,
    DiscoveryType,
    GapDiscoveryEngine,
    PatternDiscoveryEngine,
    TrendDiscoveryEngine,
)

from theo.services.api.app.persistence_models import (
    CorpusSnapshot,
    Discovery,
    Document,
    Passage,
)
from ..db.query_optimizations import query_with_monitoring


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
        discovery_repo: DiscoveryRepository,
        document_repo: DocumentRepository,
        pattern_engine: PatternDiscoveryEngine | None = None,
        contradiction_engine: ContradictionDiscoveryEngine | None = None,
        trend_engine: TrendDiscoveryEngine | None = None,
        anomaly_engine: AnomalyDiscoveryEngine | None = None,
        connection_engine: ConnectionDiscoveryEngine | None = None,
        gap_engine: GapDiscoveryEngine | None = None,
    ):
        self.discovery_repo = discovery_repo
        self.document_repo = document_repo
        self.pattern_engine = pattern_engine or PatternDiscoveryEngine()
        self.contradiction_engine = contradiction_engine or ContradictionDiscoveryEngine()
        self.trend_engine = trend_engine or TrendDiscoveryEngine()
        self.anomaly_engine = anomaly_engine or AnomalyDiscoveryEngine()
        self.connection_engine = connection_engine or ConnectionDiscoveryEngine()
        self.gap_engine = gap_engine or GapDiscoveryEngine()

    @query_with_monitoring("discoveries.list")
    def list(
        self,
        user_id: str,
        *,
        discovery_type: str | None = None,
        viewed: bool | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Discovery]:
        stmt = select(Discovery).where(Discovery.user_id == user_id)
        if discovery_type:
            stmt = stmt.where(Discovery.discovery_type == discovery_type)
        if viewed is not None:
            stmt = stmt.where(Discovery.viewed == viewed)
        stmt = stmt.order_by(Discovery.created_at.desc())
        if offset:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def mark_viewed(self, user_id: str, discovery_id: int) -> Discovery:
        discovery = self._get_user_discovery(user_id, discovery_id)
        if not discovery.viewed:
            discovery.viewed = True
            self.session.commit()
        return discovery

    def set_feedback(
        self, user_id: str, discovery_id: int, reaction: str | None
    ) -> DiscoveryDTO:
        return self.discovery_repo.set_reaction(discovery_id, user_id, reaction)

    def dismiss(self, user_id: str, discovery_id: int) -> None:
        self.discovery_repo.mark_viewed(discovery_id, user_id)
        self.discovery_repo.set_reaction(discovery_id, user_id, "dismissed")

    def refresh_user_discoveries(self, user_id: str) -> list[DiscoveryDTO]:
        documents = self.document_repo.list_with_embeddings(user_id)
        if not documents:
            self.discovery_repo.delete_by_types(user_id, self._discoveries_to_clear())
            return []

        pattern_candidates, snapshot = self.pattern_engine.detect(documents)
        contradiction_candidates = self.contradiction_engine.detect(documents)
        anomaly_candidates = self.anomaly_engine.detect(documents)
        connection_candidates = self.connection_engine.detect(documents)
        gap_candidates = self.gap_engine.detect(documents)

        historical_snapshots = self.discovery_repo.get_recent_snapshots(
            user_id, limit=self.trend_engine.history_window - 1
        )
        trend_candidates = self.trend_engine.detect([
            *[self._snapshot_dto_to_domain(s) for s in historical_snapshots],
            snapshot,
        ])

        self.discovery_repo.delete_by_types(user_id, self._discoveries_to_clear())

        persisted: list[DiscoveryDTO] = []
        persisted.extend(
            self._persist_pattern_candidates(user_id, pattern_candidates)
        )
        persisted.extend(
            self._persist_contradiction_candidates(user_id, contradiction_candidates)
        )
        persisted.extend(self._persist_trend_candidates(user_id, trend_candidates))
        persisted.extend(self._persist_anomaly_candidates(user_id, anomaly_candidates))
        persisted.extend(
            self._persist_connection_candidates(user_id, connection_candidates)
        )
        persisted.extend(self._persist_gap_candidates(user_id, gap_candidates))

        snapshot_dto = CorpusSnapshotDTO(
            id=0,
            user_id=user_id,
            snapshot_date=snapshot.snapshot_date,
            document_count=snapshot.document_count,
            verse_coverage=dict(snapshot.verse_coverage),
            dominant_themes=dict(snapshot.dominant_themes),
            metadata=dict(snapshot.metadata),
        )
        self.discovery_repo.create_snapshot(snapshot_dto)

        return persisted

    def _persist_pattern_candidates(
        self, user_id: str, candidates: list
    ) -> list[DiscoveryDTO]:
        persisted: list[DiscoveryDTO] = []
        for candidate in candidates:
            dto = DiscoveryDTO(
                id=0,
                user_id=user_id,
                discovery_type=DiscoveryType.PATTERN.value,
                title=candidate.title,
                description=candidate.description,
                confidence=float(candidate.confidence),
                relevance_score=float(candidate.relevance_score),
                viewed=False,
                user_reaction=None,
                created_at=datetime.now(UTC),
                metadata=dict(candidate.metadata),
            )
            persisted.append(self.discovery_repo.create(dto))
        return persisted

    def _persist_contradiction_candidates(
        self, user_id: str, candidates: list
    ) -> list[DiscoveryDTO]:
        persisted: list[DiscoveryDTO] = []
        for candidate in candidates:
            metadata = {
                "document_a_id": candidate.document_a_id,
                "document_b_id": candidate.document_b_id,
                "document_a_title": candidate.document_a_title,
                "document_b_title": candidate.document_b_title,
                "claim_a": candidate.claim_a,
                "claim_b": candidate.claim_b,
                "contradiction_type": candidate.contradiction_type,
            }
            metadata.update(dict(candidate.metadata))

            dto = DiscoveryDTO(
                id=0,
                user_id=user_id,
                discovery_type=DiscoveryType.CONTRADICTION.value,
                title=candidate.title,
                description=candidate.description,
                confidence=float(candidate.confidence),
                relevance_score=float(candidate.relevance_score),
                viewed=False,
                user_reaction=None,
                created_at=datetime.now(UTC),
                metadata=metadata,
            )
            persisted.append(self.discovery_repo.create(dto))
        return persisted

    def _persist_trend_candidates(
        self, user_id: str, candidates: list
    ) -> list[DiscoveryDTO]:
        persisted: list[DiscoveryDTO] = []
        for candidate in candidates:
            dto = DiscoveryDTO(
                id=0,
                user_id=user_id,
                discovery_type=DiscoveryType.TREND.value,
                title=candidate.title,
                description=candidate.description,
                confidence=float(candidate.confidence),
                relevance_score=float(candidate.relevance_score),
                viewed=False,
                user_reaction=None,
                created_at=datetime.now(UTC),
                metadata=dict(candidate.metadata),
            )
            persisted.append(self.discovery_repo.create(dto))
        return persisted

    def _persist_anomaly_candidates(
        self, user_id: str, candidates: list
    ) -> list[DiscoveryDTO]:
        persisted: list[DiscoveryDTO] = []
        for candidate in candidates:
            metadata = dict(candidate.metadata)
            metadata.setdefault("documentId", candidate.document_id)
            metadata.setdefault("anomalyScore", candidate.anomaly_score)

            dto = DiscoveryDTO(
                id=0,
                user_id=user_id,
                discovery_type=DiscoveryType.ANOMALY.value,
                title=candidate.title,
                description=candidate.description,
                confidence=float(candidate.confidence),
                relevance_score=float(candidate.relevance_score),
                viewed=False,
                user_reaction=None,
                created_at=datetime.now(UTC),
                metadata=metadata,
            )
            persisted.append(self.discovery_repo.create(dto))
        return persisted

    def _persist_connection_candidates(
        self, user_id: str, candidates: list
    ) -> list[DiscoveryDTO]:
        persisted: list[DiscoveryDTO] = []
        for candidate in candidates:
            dto = DiscoveryDTO(
                id=0,
                user_id=user_id,
                discovery_type=DiscoveryType.CONNECTION.value,
                title=candidate.title,
                description=candidate.description,
                confidence=float(candidate.confidence),
                relevance_score=float(candidate.relevance_score),
                viewed=False,
                user_reaction=None,
                created_at=datetime.now(UTC),
                metadata=dict(candidate.metadata),
            )
            persisted.append(self.discovery_repo.create(dto))
        return persisted

    def _persist_gap_candidates(
        self, user_id: str, candidates: list
    ) -> list[DiscoveryDTO]:
        persisted: list[DiscoveryDTO] = []
        for candidate in candidates:
            metadata = dict(candidate.metadata)
            metadata.setdefault("referenceTopic", candidate.reference_topic)
            metadata.setdefault("missingKeywords", list(candidate.missing_keywords))
            metadata.setdefault("sharedKeywords", list(candidate.shared_keywords))
            metadata.setdefault("relatedDocuments", list(candidate.related_documents))

            dto = DiscoveryDTO(
                id=0,
                user_id=user_id,
                discovery_type=DiscoveryType.GAP.value,
                title=candidate.title,
                description=candidate.description,
                confidence=float(candidate.confidence),
                relevance_score=float(candidate.relevance_score),
                viewed=False,
                user_reaction=None,
                created_at=datetime.now(UTC),
                metadata=metadata,
            )
            persisted.append(self.discovery_repo.create(dto))
        return persisted

    @staticmethod
    def _snapshot_dto_to_domain(dto: CorpusSnapshotDTO):
        from theo.domain.discoveries.models import CorpusSnapshotSummary

        return CorpusSnapshotSummary(
            snapshot_date=dto.snapshot_date,
            document_count=dto.document_count,
            verse_coverage=dto.verse_coverage,
            dominant_themes=dto.dominant_themes,
            metadata=dto.metadata,
        )

    @staticmethod
    def _discoveries_to_clear() -> list[str]:
        return [
            DiscoveryType.PATTERN.value,
            DiscoveryType.CONTRADICTION.value,
            DiscoveryType.TREND.value,
            DiscoveryType.ANOMALY.value,
            DiscoveryType.CONNECTION.value,
            DiscoveryType.GAP.value,
        ]


__all__ = ["DiscoveryService"]

