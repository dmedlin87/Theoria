"""Discovery routes using new repository pattern - v1.0 API.

This is a reference implementation showing how to migrate existing routes
to use the new architectural patterns (DTOs, repositories, domain errors).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from theo.adapters.persistence.discovery_repository import SQLAlchemyDiscoveryRepository
from theo.application.dtos import DiscoveryDTO, DiscoveryListFilters
from theo.application.facades.database import get_session
from theo.application.repositories import DiscoveryRepository
from theo.domain.errors import NotFoundError

router = APIRouter()


def get_discovery_repository(
    session: Session = Depends(get_session),
) -> DiscoveryRepository:
    """Dependency injection for discovery repository.

    This factory creates a repository instance for each request,
    allowing the service layer to work with abstractions rather
    than concrete implementations.
    """
    return SQLAlchemyDiscoveryRepository(session)


@router.get("/discoveries", response_model=list[DiscoveryDTO])
def list_discoveries(
    user_id: str = Query(..., description="User ID to fetch discoveries for"),
    discovery_type: str | None = Query(None, description="Filter by discovery type"),
    viewed: bool | None = Query(None, description="Filter by viewed status"),
    min_confidence: float | None = Query(
        None, ge=0.0, le=1.0, description="Minimum confidence threshold"
    ),
    limit: int | None = Query(None, ge=1, le=100, description="Maximum results"),
    offset: int | None = Query(None, ge=0, description="Pagination offset"),
    repo: DiscoveryRepository = Depends(get_discovery_repository),
) -> list[DiscoveryDTO]:
    """List discoveries for a user with optional filters.

    This endpoint demonstrates the new architecture:
    - Works with DTOs (not ORM models)
    - Uses repository abstraction
    - Returns type-safe responses

    Example:
        GET /api/v1/discoveries?user_id=test&viewed=false&min_confidence=0.7
    """
    filters = DiscoveryListFilters(
        user_id=user_id,
        discovery_type=discovery_type,
        viewed=viewed,
        min_confidence=min_confidence,
        limit=limit,
        offset=offset,
    )

    return repo.list(filters)


@router.get("/discoveries/{discovery_id}", response_model=DiscoveryDTO)
def get_discovery(
    discovery_id: int,
    user_id: str = Query(..., description="User ID for authorization"),
    repo: DiscoveryRepository = Depends(get_discovery_repository),
) -> DiscoveryDTO:
    """Get a single discovery by ID.

    Raises:
        NotFoundError: If discovery doesn't exist or user doesn't have access
    """
    discovery = repo.get_by_id(discovery_id, user_id)

    if discovery is None:
        raise NotFoundError("Discovery", discovery_id)

    return discovery


@router.post("/discoveries/{discovery_id}/view", response_model=DiscoveryDTO)
def mark_discovery_viewed(
    discovery_id: int,
    user_id: str = Query(..., description="User ID for authorization"),
    repo: DiscoveryRepository = Depends(get_discovery_repository),
) -> DiscoveryDTO:
    """Mark a discovery as viewed.

    This updates the viewed flag and returns the updated discovery.
    Domain errors are automatically converted to appropriate HTTP responses.
    """
    try:
        return repo.mark_viewed(discovery_id, user_id)
    except LookupError:
        raise NotFoundError("Discovery", discovery_id)


@router.post("/discoveries/{discovery_id}/feedback", response_model=DiscoveryDTO)
def set_discovery_feedback(
    discovery_id: int,
    reaction: str | None = Query(None, description="User reaction: helpful, not_helpful, dismissed"),
    user_id: str = Query(..., description="User ID for authorization"),
    repo: DiscoveryRepository = Depends(get_discovery_repository),
) -> DiscoveryDTO:
    """Set user feedback/reaction on a discovery.

    Valid reactions:
    - helpful: Discovery was useful
    - not_helpful: Discovery wasn't relevant
    - dismissed: User doesn't want to see it again
    - null: Clear existing reaction
    """
    try:
        return repo.set_reaction(discovery_id, user_id, reaction)
    except LookupError:
        raise NotFoundError("Discovery", discovery_id)


__all__ = ["router", "get_discovery_repository"]
