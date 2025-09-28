"""Routes exposing digest operations."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...ai.digest_service import DigestService
from ...analytics.topics import TopicDigest
from ...core.database import get_session
from ...core.settings import get_settings


router = APIRouter()


@router.get("/digest", response_model=TopicDigest | None, response_model_exclude_none=True)
def get_topic_digest(session: Session = Depends(get_session)):
    """Return the cached digest, generating it if missing."""

    settings = get_settings()
    ttl = timedelta(seconds=settings.topic_digest_ttl_seconds)
    service = DigestService(session, ttl=ttl)
    return service.ensure_latest()


@router.post("/digest", response_model=TopicDigest)
def refresh_topic_digest(
    hours: int = Query(default=168, ge=1, description="Lookback window in hours"),
    session: Session = Depends(get_session),
):
    """Regenerate the digest for the requested lookback window."""

    settings = get_settings()
    ttl = timedelta(seconds=settings.topic_digest_ttl_seconds)
    service = DigestService(session, ttl=ttl)
    return service.refresh(hours)

