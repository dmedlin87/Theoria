"""API endpoints surfacing user discoveries."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from theo.adapters.persistence.discovery_repository import SQLAlchemyDiscoveryRepository
from theo.adapters.persistence.document_repository import SQLAlchemyDocumentRepository
from theo.application.facades.database import get_session

from ..discoveries import DiscoveryService
from ..models.discoveries import (
    DiscoveryFeedbackRequest,
    DiscoveryListResponse,
    DiscoveryResponse,
    DiscoveryStats,
)
from ..security import Principal, require_principal

router = APIRouter()


def _require_user_subject(principal: Principal) -> str:
    subject = principal.get("subject")
    if not subject:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing principal")
    return subject


def get_discovery_service(
    session: Session = Depends(get_session),
) -> DiscoveryService:
    discovery_repo = SQLAlchemyDiscoveryRepository(session)
    document_repo = SQLAlchemyDocumentRepository(session)
    return DiscoveryService(discovery_repo, document_repo)


def _build_stats(discoveries: list[DiscoveryResponse]) -> DiscoveryStats:
    total = len(discoveries)
    unviewed = sum(1 for item in discoveries if not item.viewed)
    by_type: dict[str, int] = {}
    for item in discoveries:
        by_type[item.type] = by_type.get(item.type, 0) + 1
    average_confidence = 0.0
    if total:
        average_confidence = sum(item.confidence for item in discoveries) / total
    return DiscoveryStats(
        total=total,
        unviewed=unviewed,
        byType=by_type,
        averageConfidence=round(average_confidence, 4),
    )


@router.get("/", response_model=DiscoveryListResponse)
def list_discoveries(
    discovery_type: str | None = Query(default=None),
    viewed: bool | None = Query(default=None),
    principal: Principal = Depends(require_principal),
    service: DiscoveryService = Depends(get_discovery_service),
) -> DiscoveryListResponse:
    user_id = _require_user_subject(principal)
    records = service.list(user_id, discovery_type=discovery_type, viewed=viewed)
    payload = [DiscoveryResponse.model_validate(record) for record in records]
    stats = _build_stats(payload)
    return DiscoveryListResponse(discoveries=payload, stats=stats)


@router.post("/{discovery_id}/view", status_code=status.HTTP_204_NO_CONTENT)
def mark_discovery_viewed(
    discovery_id: int,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
    service: DiscoveryService = Depends(get_discovery_service),
) -> Response:
    user_id = _require_user_subject(principal)
    try:
        service.mark_viewed(user_id, discovery_id)
        session.commit()
    except LookupError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery not found") from exc
    except Exception:
        session.rollback()
        # Intentionally catch any unexpected application error so the
        # transaction is rolled back before the exception bubbles up.
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{discovery_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
def submit_discovery_feedback(
    discovery_id: int,
    payload: DiscoveryFeedbackRequest,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
    service: DiscoveryService = Depends(get_discovery_service),
) -> Response:
    user_id = _require_user_subject(principal)
    reaction = "helpful" if payload.helpful else "not_helpful"
    try:
        service.set_feedback(user_id, discovery_id, reaction)
        session.commit()
    except LookupError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery not found") from exc
    except Exception:
        session.rollback()
        # Intentionally catch any unexpected application error so the
        # transaction is rolled back before the exception bubbles up.
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{discovery_id}", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_discovery(
    discovery_id: int,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
    service: DiscoveryService = Depends(get_discovery_service),
) -> Response:
    user_id = _require_user_subject(principal)
    try:
        service.dismiss(user_id, discovery_id)
        session.commit()
    except LookupError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery not found") from exc
    except Exception:
        session.rollback()
        # Intentionally catch any unexpected application error so the
        # transaction is rolled back before the exception bubbles up.
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
