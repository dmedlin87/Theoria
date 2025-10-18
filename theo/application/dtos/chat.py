"""DTOs for chat session persistence interactions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ChatSessionDTO:
    """Lightweight representation of a persisted chat session."""

    id: str
    user_id: str | None
    memory_snippets: list[dict[str, Any]]
    updated_at: datetime


__all__ = ["ChatSessionDTO"]

