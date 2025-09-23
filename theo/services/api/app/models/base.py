"""Shared Pydantic schemas used across API responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    """Base schema configuration enabling ORM compatibility."""

    model_config = ConfigDict(from_attributes=True)


class TimestampedModel(APIModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = Field(default=None)


class Passage(APIModel):
    id: str
    document_id: str
    text: str
    osis_ref: str | None = None
    page_no: int | None = None
    t_start: float | None = None
    t_end: float | None = None
    score: float | None = Field(default=None, description="Optional retrieval score")
    meta: dict[str, Any] | None = None
