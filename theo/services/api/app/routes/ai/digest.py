"""Routes exposing digest operations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...ai.digest_service import DigestService
from ...analytics.topics import TopicDigest
from ...core.database import get_session


router = APIRouter()


@router.get("/digest", response_model=TopicDigest | None, response_model_exclude_none=True)
def get_topic_digest(session: Session = Depends(get_session)):
    """Return the cached digest, generating it if missing."""

    service = DigestService(session)
    return service.ensure_latest()


@router.post("/digest", response_model=TopicDigest)
def refresh_topic_digest(
    hours: int = Query(default=168, ge=1, description="Lookback window in hours"),
    session: Session = Depends(get_session),
):
    """Regenerate the digest for the requested lookback window."""

    service = DigestService(session)
    return service.refresh(hours)

