"""Repository abstraction for ingestion job bookkeeping."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from theo.application.dtos import IngestionJobDTO


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
    ) -> IngestionJobDTO | None:
        """Update status metadata for the ingestion job and return updated DTO."""

    @abstractmethod
    def set_payload(self, job_id: str, payload: dict[str, Any]) -> IngestionJobDTO | None:
        """Replace the payload associated with the ingestion job and return updated DTO."""

    @abstractmethod
    def merge_payload(self, job_id: str, payload: dict[str, Any]) -> IngestionJobDTO | None:
        """Merge *payload* into the stored job payload and return updated DTO."""


__all__ = ["IngestionJobRepository"]

