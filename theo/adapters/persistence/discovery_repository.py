"""SQLAlchemy implementation of DiscoveryRepository.

This adapter implements the repository interface using SQLAlchemy ORM,
translating between DTOs and database models.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from theo.application.dtos import (
    CorpusSnapshotDTO,
    DiscoveryDTO,
    DiscoveryListFilters,
)
from theo.application.observability import trace_repository_call
from theo.application.repositories.discovery_repository import DiscoveryRepository

from .mappers import (
    corpus_snapshot_to_dto,
    discovery_to_dto,
    dto_to_discovery,
)
from .models import CorpusSnapshot, Discovery


class SQLAlchemyDiscoveryRepository(DiscoveryRepository):
    """SQLAlchemy-based discovery repository implementation."""

    def __init__(self, session: Session):
        self.session = session

    def list(self, filters: DiscoveryListFilters) -> list[DiscoveryDTO]:
        """Retrieve discoveries matching the provided filters."""
        with trace_repository_call(
            "discovery",
            "list",
            attributes={
                "user_id": filters.user_id,
                "discovery_type": filters.discovery_type,
                "viewed": filters.viewed,
                "limit": filters.limit,
                "offset": filters.offset,
            },
        ) as trace:
            stmt = select(Discovery).where(Discovery.user_id == filters.user_id)

            if filters.discovery_type:
                stmt = stmt.where(Discovery.discovery_type == filters.discovery_type)

            if filters.viewed is not None:
                stmt = stmt.where(Discovery.viewed == filters.viewed)

            if filters.min_confidence is not None:
                stmt = stmt.where(Discovery.confidence >= filters.min_confidence)

            stmt = stmt.order_by(Discovery.created_at.desc())

            if filters.limit:
                stmt = stmt.limit(filters.limit)

            if filters.offset:
                stmt = stmt.offset(filters.offset)

            results = self.session.scalars(stmt).all()
            trace.record_result_count(len(results))
            return [discovery_to_dto(r) for r in results]

    def get_by_id(self, discovery_id: int, user_id: str) -> DiscoveryDTO | None:
        """Retrieve a single discovery by ID and user."""
        with trace_repository_call(
            "discovery",
            "get_by_id",
            attributes={"discovery_id": discovery_id, "user_id": user_id},
        ) as trace:
            stmt = select(Discovery).where(
                Discovery.id == discovery_id,
                Discovery.user_id == user_id,
            )
            result = self.session.scalars(stmt).one_or_none()
            trace.set_attribute("hit", result is not None)
            trace.record_result_count(1 if result else 0)
            return discovery_to_dto(result) if result else None

    def create(self, discovery: DiscoveryDTO) -> DiscoveryDTO:
        """Persist a new discovery and return the saved version."""
        created = self.create_many([discovery])
        return created[0]

    def create_many(self, discoveries: Sequence[DiscoveryDTO]) -> list[DiscoveryDTO]:
        """Persist multiple discoveries in a single batch."""
        with trace_repository_call(
            "discovery",
            "create_many",
            attributes={"count": len(discoveries)},
        ) as trace:
            if not discoveries:
                trace.record_result_count(0)
                return []
            models = [dto_to_discovery(dto) for dto in discoveries]
            self.session.add_all(models)
            self.session.flush()  # Assign IDs in a single round-trip
            trace.record_result_count(len(models))
            return [discovery_to_dto(model) for model in models]

    def update(self, discovery: DiscoveryDTO) -> DiscoveryDTO:
        """Update an existing discovery."""
        with trace_repository_call(
            "discovery",
            "update",
            attributes={"discovery_id": discovery.id},
        ) as trace:
            model = self.session.get(Discovery, discovery.id)
            if model is None:
                trace.set_attribute("missing", True)
                raise LookupError(f"Discovery {discovery.id} not found")

            # Update mutable fields
            model.title = discovery.title
            model.description = discovery.description
            model.confidence = discovery.confidence
            model.relevance_score = discovery.relevance_score
            model.viewed = discovery.viewed
            model.user_reaction = discovery.user_reaction
            model.meta = dict(discovery.metadata) if discovery.metadata else None

            self.session.flush()
            trace.record_result_count(1)
            return discovery_to_dto(model)

    def delete_by_types(self, user_id: str, discovery_types: list[str]) -> int:
        """Delete all discoveries of specified types for a user."""
        with trace_repository_call(
            "discovery",
            "delete_by_types",
            attributes={"user_id": user_id, "types": tuple(discovery_types)},
        ) as trace:
            result = self.session.execute(
                delete(Discovery).where(
                    Discovery.user_id == user_id,
                    Discovery.discovery_type.in_(discovery_types),
                )
            )
            deleted = result.rowcount
            trace.record_result_count(deleted or 0)
            return deleted

    def mark_viewed(self, discovery_id: int, user_id: str) -> DiscoveryDTO:
        """Mark a discovery as viewed."""
        with trace_repository_call(
            "discovery",
            "mark_viewed",
            attributes={"discovery_id": discovery_id, "user_id": user_id},
        ) as trace:
            model = self.session.get(Discovery, discovery_id)
            if model is None or model.user_id != user_id:
                trace.set_attribute("missing", True)
                raise LookupError(f"Discovery {discovery_id} not found for user {user_id}")

            model.viewed = True
            self.session.flush()
            trace.record_result_count(1)
            return discovery_to_dto(model)

    def set_reaction(
        self, discovery_id: int, user_id: str, reaction: str | None
    ) -> DiscoveryDTO:
        """Set user reaction on a discovery."""
        with trace_repository_call(
            "discovery",
            "set_reaction",
            attributes={
                "discovery_id": discovery_id,
                "user_id": user_id,
                "reaction": reaction,
            },
        ) as trace:
            model = self.session.get(Discovery, discovery_id)
            if model is None or model.user_id != user_id:
                trace.set_attribute("missing", True)
                raise LookupError(f"Discovery {discovery_id} not found for user {user_id}")

            model.user_reaction = reaction
            self.session.flush()
            trace.record_result_count(1)
            return discovery_to_dto(model)

    def create_snapshot(self, snapshot: CorpusSnapshotDTO) -> CorpusSnapshotDTO:
        """Persist a corpus snapshot."""
        with trace_repository_call(
            "discovery",
            "create_snapshot",
            attributes={"user_id": snapshot.user_id},
        ) as trace:
            model = CorpusSnapshot(
                user_id=snapshot.user_id,
                snapshot_date=snapshot.snapshot_date,
                document_count=snapshot.document_count,
                verse_coverage=dict(snapshot.verse_coverage),
                dominant_themes=dict(snapshot.dominant_themes),
                meta=dict(snapshot.metadata) if snapshot.metadata else None,
            )
            self.session.add(model)
            self.session.flush()
            trace.record_result_count(1)
            return corpus_snapshot_to_dto(model)

    def get_recent_snapshots(
        self, user_id: str, limit: int
    ) -> list[CorpusSnapshotDTO]:
        """Retrieve recent corpus snapshots for trend analysis."""
        with trace_repository_call(
            "discovery",
            "get_recent_snapshots",
            attributes={"user_id": user_id, "limit": limit},
        ) as trace:
            stmt = (
                select(CorpusSnapshot)
                .where(CorpusSnapshot.user_id == user_id)
                .order_by(CorpusSnapshot.snapshot_date.desc())
                .limit(limit)
            )
            results = list(self.session.scalars(stmt))
            trace.record_result_count(len(results))
            results.reverse()  # Return oldest to newest
            return [corpus_snapshot_to_dto(r) for r in results]


__all__ = ["SQLAlchemyDiscoveryRepository"]
