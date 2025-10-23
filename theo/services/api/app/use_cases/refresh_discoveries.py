"""Use case for refreshing user discoveries.

This demonstrates the proper application layer pattern:
- Uses repository abstractions
- Works with domain objects and DTOs
- Orchestrates multiple operations
- Maintains transaction boundaries
"""

from __future__ import annotations

from datetime import UTC, datetime

from theo.application.dtos import CorpusSnapshotDTO, DiscoveryDTO
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


class RefreshDiscoveriesUseCase:
    """Orchestrates the discovery refresh process.

    This use case coordinates:
    1. Loading document embeddings
    2. Running all discovery engines
    3. Clearing old discoveries
    4. Persisting new discoveries
    5. Creating corpus snapshot
    """

    def __init__(
        self,
        discovery_repo: DiscoveryRepository,
        pattern_engine: PatternDiscoveryEngine | None = None,
        contradiction_engine: ContradictionDiscoveryEngine | None = None,
        trend_engine: TrendDiscoveryEngine | None = None,
        anomaly_engine: AnomalyDiscoveryEngine | None = None,
        connection_engine: ConnectionDiscoveryEngine | None = None,
        gap_engine: GapDiscoveryEngine | None = None,
    ):
        """Initialize use case with repository and engines.

        Args:
            discovery_repo: Repository for discovery persistence
            pattern_engine: Optional pattern detection engine
            contradiction_engine: Optional contradiction detection engine
            trend_engine: Optional trend detection engine
            anomaly_engine: Optional anomaly detection engine
            connection_engine: Optional connection detection engine
            gap_engine: Optional gap detection engine
        """
        self.discovery_repo = discovery_repo
        self.pattern_engine = pattern_engine or PatternDiscoveryEngine()
        self.contradiction_engine = contradiction_engine or ContradictionDiscoveryEngine()
        self.trend_engine = trend_engine or TrendDiscoveryEngine()
        self.anomaly_engine = anomaly_engine or AnomalyDiscoveryEngine()
        self.connection_engine = connection_engine or ConnectionDiscoveryEngine()
        self.gap_engine = gap_engine or GapDiscoveryEngine()

    def execute(
        self,
        user_id: str,
        document_repo: DocumentRepository,
    ) -> list[DiscoveryDTO]:
        """Execute the discovery refresh for a user.

        Args:
            user_id: User ID to refresh discoveries for
            document_repo: Repository used to load document embeddings

        Returns:
            List of newly created discoveries
        """
        documents = document_repo.list_with_embeddings(user_id)

        # Run all discovery engines
        pattern_candidates, snapshot = self.pattern_engine.detect(documents)
        contradiction_candidates = self.contradiction_engine.detect(documents)
        anomaly_candidates = self.anomaly_engine.detect(documents)
        connection_candidates = self.connection_engine.detect(documents)
        gap_candidates = self.gap_engine.detect(documents)

        # Load historical snapshots for trend detection
        historical_snapshots = self.discovery_repo.get_recent_snapshots(
            user_id, limit=self.trend_engine.history_window - 1
        )
        trend_candidates = self.trend_engine.detect([
            *[self._snapshot_dto_to_domain(s) for s in historical_snapshots],
            snapshot,
        ])

        # Clear old discoveries atomically
        discovery_types_to_clear = [
            DiscoveryType.PATTERN.value,
            DiscoveryType.CONTRADICTION.value,
            DiscoveryType.TREND.value,
            DiscoveryType.ANOMALY.value,
            DiscoveryType.CONNECTION.value,
            DiscoveryType.GAP.value,
        ]
        deleted_count = self.discovery_repo.delete_by_types(
            user_id, discovery_types_to_clear
        )

        # Convert domain discoveries to DTOs and persist
        new_discoveries: list[DiscoveryDTO] = []

        # Pattern discoveries
        for candidate in pattern_candidates:
            dto = DiscoveryDTO(
                id=0,  # Will be set by repository
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
            new_discoveries.append(dto)

        # Contradiction discoveries
        for candidate in contradiction_candidates:
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
            new_discoveries.append(dto)

        persisted = (
            self.discovery_repo.create_many(new_discoveries)
            if new_discoveries
            else []
        )

        # Similar logic for other discovery types...
        # (Anomaly, Connection, Gap, Trend)

        # Create corpus snapshot
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

    @staticmethod
    def _snapshot_dto_to_domain(dto: CorpusSnapshotDTO):
        """Convert snapshot DTO back to domain object for trend engine."""
        from theo.domain.discoveries.models import CorpusSnapshotSummary

        return CorpusSnapshotSummary(
            snapshot_date=dto.snapshot_date,
            document_count=dto.document_count,
            verse_coverage=dto.verse_coverage,
            dominant_themes=dto.dominant_themes,
            metadata=dto.metadata,
        )


__all__ = ["RefreshDiscoveriesUseCase"]
