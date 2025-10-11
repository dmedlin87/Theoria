"""Shared Pydantic schemas used across API responses.

The base model explicitly clears Pydantic's protected namespaces so response
schemas can expose attributes like ``model_`` without triggering warnings.
Future fields should avoid relying on protected names unless intentional.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Self

from pydantic import ConfigDict, Field

if TYPE_CHECKING:
    class BaseModel:
        """Typed façade mirroring :class:`pydantic.BaseModel`."""

        model_config: ClassVar[ConfigDict]

        @classmethod
        def model_validate(
            cls,
            obj: Any,
            *,
            strict: bool | None = None,
            from_attributes: bool | None = None,
            context: dict[str, Any] | None = None,
        ) -> Self: ...

        @classmethod
        def model_validate_json(
            cls,
            json_data: str | bytes | bytearray,
            *,
            strict: bool | None = None,
            context: dict[str, Any] | None = None,
        ) -> Self: ...

        @classmethod
        def model_construct(
            cls,
            _fields_set: set[str] | None = None,
            **values: Any,
        ) -> Self: ...

        def model_copy(
            self,
            *,
            update: dict[str, Any] | None = None,
            deep: bool = False,
        ) -> Self: ...

else:  # pragma: no cover - executed only at runtime
    from pydantic import BaseModel as _PydanticBaseModel

    class BaseModel(_PydanticBaseModel):
        """Runtime subclass that inherits from :class:`pydantic.BaseModel`."""

        pass


class APIModel(BaseModel):
    """Base schema configuration enabling ORM compatibility."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


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


__all__ = ["BaseModel", "APIModel", "TimestampedModel", "Passage"]
