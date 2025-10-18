"""Repository abstraction for ingestion job bookkeeping."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IngestionJobRepository(ABC):
    """Interface for updating ingestion job records."""

    @abstractmethod
    def update_status(
        self,
        job_id: str,
        *,
        status: str,
        error: str | None = None,
        document_id: str | None = None,
    ) -> None:
        """Update status metadata for the ingestion job."""

    @abstractmethod
    def set_payload(self, job_id: str, payload: dict[str, Any]) -> None:
        """Replace the payload associated with the ingestion job."""

    @abstractmethod
    def merge_payload(self, job_id: str, payload: dict[str, Any]) -> None:
        """Merge *payload* into the stored job payload."""


__all__ = ["IngestionJobRepository"]

