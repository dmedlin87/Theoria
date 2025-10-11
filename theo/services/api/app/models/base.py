"""Shared Pydantic schemas used across API responses.

The base model explicitly clears Pydantic's protected namespaces so response
schemas can expose attributes like ``model_`` without triggering warnings.
Future fields should avoid relying on protected names unless intentional.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    """Base schema configuration enabling ORM compatibility."""

    model_config = ConfigDict(
        from_attributes=True,
        protected_namespaces=(),
    )


class TimestampedModel(APIModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = Field(default=None)


class Passage(APIModel):
    id: str
    document_id: str
    text: str
    raw_text: str | None = Field(default=None, exclude=True)
    osis_ref: str | None = None
    start_char: int | None = None
    end_char: int | None = None
    page_no: int | None = None
    t_start: float | None = None
    t_end: float | None = None
    score: float | None = Field(default=None, description="Optional retrieval score")
    meta: dict[str, Any] | None = None
