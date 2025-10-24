"""Domain-specific exceptions and HTTP response helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from fastapi.responses import JSONResponse


class Severity(str, Enum):
    """Enumerate error severities for downstream telemetry."""

    USER = "user"
    TRANSIENT = "transient"
    CRITICAL = "critical"


@dataclass(slots=True)
class TheoError(Exception):
    """Base class for domain errors raised by the API layer."""

    message: str
    code: str
    status_code: int
    severity: Severity = Severity.CRITICAL
    hint: str | None = None
    data: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:  # pragma: no cover - defensive guard
        if not self.code:
            raise ValueError("TheoError requires a non-empty error code")

    def to_payload(self, trace_id: str | None = None) -> dict[str, Any]:
        """Return a serialisable representation for HTTP responses."""

        payload: dict[str, Any] = {
            "error": {
                "code": self.code,
                "message": self.message,
                "severity": self.severity.value,
            }
        }
        # Include the human-readable message at the top level to maintain the
        # legacy ``detail`` field expected by older clients and tests.
        payload["detail"] = self.message
        if self.hint:
            payload["error"]["hint"] = self.hint
        if self.data:
            payload["error"]["data"] = dict(self.data)
        if trace_id:
            payload["trace_id"] = trace_id
        return payload

    def to_response(self, trace_id: str | None = None) -> JSONResponse:
        """Build a JSON response compatible with FastAPI's handlers."""

        return JSONResponse(status_code=self.status_code, content=self.to_payload(trace_id))


@dataclass(slots=True)
class IngestionError(TheoError):
    """Domain error raised by ingestion routers and pipelines."""

    severity: Severity = field(default=Severity.CRITICAL)


@dataclass(slots=True)
class RetrievalError(TheoError):
    """Domain error for document/search retrieval routes."""

    severity: Severity = field(default=Severity.CRITICAL)


@dataclass(slots=True)
class ExportError(TheoError):
    """Domain error covering export flows."""

    severity: Severity = field(default=Severity.CRITICAL)


@dataclass(slots=True)
class AIWorkflowError(TheoError):
    """Domain error raised by AI workflow and chat routes."""

    severity: Severity = field(default=Severity.USER)


class DatabaseMigrationRequiredError(TheoError):
    """Error raised when a required database migration is missing."""

    def __init__(self, message: str, *, hint: str | None = None):
        super().__init__(
            message=message,
            code="DATABASE_MIGRATION_REQUIRED",
            status_code=500,
            severity=Severity.CRITICAL,
            hint=hint,
        )


__all__ = [
    "TheoError",
    "IngestionError",
    "RetrievalError",
    "ExportError",
    "AIWorkflowError",
    "DatabaseMigrationRequiredError",
    "Severity",
]

