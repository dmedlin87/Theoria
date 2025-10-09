"""Custom SQLAlchemy types for vector and text search support."""

from __future__ import annotations

from typing import Any, Sequence, TYPE_CHECKING

from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.sql import sqltypes
from sqlalchemy.types import TEXT

if TYPE_CHECKING:  # pragma: no cover - typing helpers
    from typing import Generic, TypeVar

    from sqlalchemy.sql.type_api import TypeEngine

    T_co = TypeVar("T_co")

    class _TypeDecorator(Generic[T_co]):  # noqa: D401 - documentation inherited
        """Typed protocol representing ``sqlalchemy.TypeDecorator``."""

        cache_ok: bool
        impl: TypeEngine[Any]

        def __init__(self, *args: Any, **kwargs: Any) -> None: ...

        def load_dialect_impl(self, dialect: Any) -> TypeEngine[Any]: ...

        def process_bind_param(self, value: Any, dialect: Any) -> Any: ...

        def process_result_value(self, value: Any, dialect: Any) -> T_co: ...

else:  # pragma: no cover - runtime import
    from sqlalchemy.types import TypeDecorator as _TypeDecorator


class VectorType(_TypeDecorator[list[float] | None]):
    """Database-agnostic representation for pgvector columns."""

    cache_ok = True

    def __init__(self, dimension: int) -> None:
        super().__init__()
        self.dimension = dimension

    impl = SQLiteJSON

    def load_dialect_impl(self, dialect: Any) -> sqltypes.TypeEngine[Any]:
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import VECTOR

            return dialect.type_descriptor(VECTOR(self.dimension))
        if dialect.name == "sqlite":
            return dialect.type_descriptor(SQLiteJSON())
        return dialect.type_descriptor(sqltypes.JSON())

    def process_bind_param(self, value: Sequence[float] | None, dialect: Any) -> Any:
        if value is None:
            return None
        return [float(component) for component in value]

    def process_result_value(self, value: Any, dialect: Any) -> list[float] | None:
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
        try:
            return [float(component) for component in list(value)]
        except (TypeError, ValueError):
            return None


class TSVectorType(_TypeDecorator[str | None]):
    """Cross-database representation for PostgreSQL tsvector columns."""

    cache_ok = True
    impl = TEXT

    def load_dialect_impl(self, dialect: Any) -> sqltypes.TypeEngine[Any]:
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import TSVECTOR

            return dialect.type_descriptor(TSVECTOR())
        return dialect.type_descriptor(TEXT())

    def process_bind_param(self, value: str | None, dialect: Any) -> Any:
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)
