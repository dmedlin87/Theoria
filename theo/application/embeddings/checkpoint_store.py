"""Lightweight persistence helpers for embedding rebuild checkpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Mapping

__all__ = [
    "CheckpointError",
    "EmbeddingCheckpoint",
    "load_checkpoint",
    "save_checkpoint",
]


_LOGGER = logging.getLogger(__name__)


class CheckpointError(ValueError):
    """Raised when a checkpoint payload cannot be parsed or validated."""


def _ensure_int(name: str, value: Any) -> int:
    if isinstance(value, bool):  # bool is subclass of int
        raise CheckpointError(f"{name} must be an integer")
    try:
        coerced = int(value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise CheckpointError(f"{name} must be an integer") from exc
    if coerced < 0:
        raise CheckpointError(f"{name} must be non-negative")
    return coerced


def _ensure_optional_str(name: str, value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    raise CheckpointError(f"{name} must be a string or null")


def _ensure_metadata(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise CheckpointError("metadata must be a mapping")
    metadata = dict(value)
    for key in metadata:
        if not isinstance(key, str):
            raise CheckpointError("metadata keys must be strings")
    return metadata


def _ensure_datetime(name: str, value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
        except ValueError as exc:
            raise CheckpointError(f"{name} must be an ISO formatted datetime") from exc
    else:  # pragma: no cover - defensive
        raise CheckpointError(f"{name} must be an ISO formatted datetime")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


@dataclass(slots=True)
class EmbeddingCheckpoint:
    """Simple container for embedding rebuild checkpoint progress."""

    processed: int
    total: int
    last_id: str | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def build(
        cls,
        *,
        processed: int,
        total: int,
        last_id: str | None,
        metadata: Mapping[str, Any] | None,
        previous: "EmbeddingCheckpoint" | None = None,
    ) -> "EmbeddingCheckpoint":
        processed_count = _ensure_int("processed", processed)
        total_count = _ensure_int("total", total)
        if processed_count > total_count:
            raise CheckpointError("processed cannot exceed total")
        now = datetime.now(timezone.utc)
        created_at = previous.created_at if previous else now
        return cls(
            processed=processed_count,
            total=total_count,
            last_id=_ensure_optional_str("last_id", last_id),
            metadata=_ensure_metadata(metadata),
            created_at=created_at,
            updated_at=now,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "processed": self.processed,
            "total": self.total,
            "last_id": self.last_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "EmbeddingCheckpoint":
        processed = _ensure_int("processed", payload.get("processed"))
        total = _ensure_int("total", payload.get("total"))
        if processed > total:
            raise CheckpointError("processed cannot exceed total")
        last_id = _ensure_optional_str("last_id", payload.get("last_id"))
        metadata = _ensure_metadata(payload.get("metadata"))
        created_at = _ensure_datetime("created_at", payload.get("created_at"))
        updated_at = _ensure_datetime("updated_at", payload.get("updated_at"))
        if updated_at < created_at:
            raise CheckpointError("updated_at cannot be earlier than created_at")
        return cls(
            processed=processed,
            total=total,
            last_id=last_id,
            metadata=metadata,
            created_at=created_at,
            updated_at=updated_at,
        )


def load_checkpoint(path: Path, *, strict: bool = False) -> EmbeddingCheckpoint | None:
    """Load a checkpoint from disk.

    When *strict* is False invalid payloads return ``None`` with a warning.
    When *strict* is True validation errors raise :class:`CheckpointError`.
    """

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        if strict:
            raise CheckpointError(f"Invalid JSON in checkpoint {path}: {exc}") from exc
        _LOGGER.warning("Invalid JSON in checkpoint %s: %s", path, exc)
        return None

    if not isinstance(payload, Mapping):
        message = (
            f"Invalid payload type in checkpoint {path}: expected mapping, got {type(payload)}"
        )
        if strict:
            raise CheckpointError(message)
        _LOGGER.warning(message)
        return None

    try:
        return EmbeddingCheckpoint.from_mapping(payload)
    except CheckpointError as exc:
        if strict:
            raise
        _LOGGER.warning("Invalid checkpoint %s: %s", path, exc)
        return None


def save_checkpoint(path: Path, checkpoint: EmbeddingCheckpoint) -> None:
    """Persist *checkpoint* to *path* using a simple JSON structure."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = checkpoint.to_payload()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
