"""Custom SQLAlchemy types for vector and text search support."""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.sql import sqltypes
from sqlalchemy.types import TEXT, TypeDecorator


class VectorType(TypeDecorator[list[float] | None]):
    """Database-agnostic representation for pgvector columns."""

    cache_ok = True

    def __init__(self, dimension: int) -> None:
        super().__init__()
        self.dimension = dimension

    impl = SQLiteJSON

    def load_dialect_impl(self, dialect):  # type: ignore[override]
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import VECTOR  # type: ignore

            return dialect.type_descriptor(VECTOR(self.dimension))
        if dialect.name == "sqlite":
            return dialect.type_descriptor(SQLiteJSON())
        return dialect.type_descriptor(sqltypes.JSON())

    def process_bind_param(self, value: Sequence[float] | None, dialect) -> Any:  # type: ignore[override]
        if value is None:
            return None
        return [float(component) for component in value]

    def process_result_value(self, value: Any, dialect) -> list[float] | None:  # type: ignore[override]
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return [float(component) for component in value]
        if isinstance(value, str):
            # Some drivers may return vectors as strings like "[0.1,0.2]".
            stripped = value.strip().strip("[]")
            if not stripped:
                return []
            return [float(component) for component in stripped.split(",")]
        return value


class TSVectorType(TypeDecorator[str | None]):
    """Cross-database representation for PostgreSQL tsvector columns."""

    cache_ok = True
    impl = TEXT

    def load_dialect_impl(self, dialect):  # type: ignore[override]
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import TSVECTOR  # type: ignore

            return dialect.type_descriptor(TSVECTOR())
        return dialect.type_descriptor(TEXT())

    def process_bind_param(self, value: str | None, dialect) -> Any:  # type: ignore[override]
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: Any, dialect) -> str | None:  # type: ignore[override]
        if value is None:
            return None
        return str(value)
