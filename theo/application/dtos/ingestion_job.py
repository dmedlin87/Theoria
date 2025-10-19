"""DTOs describing ingestion job state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class IngestionJobDTO:
    """Immutable representation of an ingestion job record."""

    id: str
    job_type: str
    status: str
    document_id: str | None
    task_id: str | None
    error: str | None
    payload: dict[str, Any] | None
    args_hash: str | None
    scheduled_at: datetime | None
    created_at: datetime
    updated_at: datetime


__all__ = ["IngestionJobDTO"]

