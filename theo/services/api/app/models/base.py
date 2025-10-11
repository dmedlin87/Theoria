"""Shared Pydantic schemas used across API responses.

The base model keeps Pydantic's default protected namespaces so response
schemas still gain access to safe ``model_*`` attributes while avoiding
accidental overrides of core ``BaseModel`` methods like :meth:`model_dump`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    """Base schema configuration enabling ORM compatibility."""

    # Allow ORM population but retain default protected namespaces.  Clearing
    # them entirely makes it possible to shadow ``BaseModel`` methods
    # (``model_dump``/``model_validate``), which removes those callables from
    # the instance and breaks serialization.
    model_config = ConfigDict(
        from_attributes=True,
        protected_namespaces=("model_validate", "model_dump"),
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
