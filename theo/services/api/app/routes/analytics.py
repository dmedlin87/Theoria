"""Routes for client-side analytics ingestion."""

from __future__ import annotations

from fastapi import APIRouter, status

from ..analytics.telemetry import record_client_telemetry
from ..models.analytics import TelemetryBatch

router = APIRouter()


@router.post("/telemetry", status_code=status.HTTP_202_ACCEPTED)
def ingest_client_telemetry(payload: TelemetryBatch) -> dict[str, str]:
    """Accept batched telemetry measurements emitted by the client."""

    record_client_telemetry(payload)
    return {"status": "accepted"}
