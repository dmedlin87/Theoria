"""Routes for client-side analytics ingestion."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from theo.application.facades.database import get_session

from ..analytics.telemetry import record_client_telemetry, record_feedback_from_payload
from ..models.analytics import FeedbackEventPayload, TelemetryBatch

router = APIRouter()


@router.post("/telemetry", status_code=status.HTTP_202_ACCEPTED)
def ingest_client_telemetry(payload: TelemetryBatch) -> dict[str, str]:
    """Accept batched telemetry measurements emitted by the client."""

    record_client_telemetry(payload)
    return {"status": "accepted"}


@router.post("/feedback", status_code=status.HTTP_202_ACCEPTED)
def ingest_feedback_event(
    payload: FeedbackEventPayload,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Persist structured user feedback events for downstream analysis."""

    try:
        record_feedback_from_payload(session, payload)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"status": "accepted"}
