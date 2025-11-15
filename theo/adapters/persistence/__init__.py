"""Persistence adapters providing database bindings and utilities."""
from __future__ import annotations

from .base_repository import BaseRepository

try:  # pragma: no cover - optional SQLAlchemy dependency in lightweight tests
    from .models import Base
except ModuleNotFoundError:  # pragma: no cover - fallback when SQLAlchemy missing
    class _MissingBase:  # type: ignore[no-redef]
        def __getattr__(self, name: str) -> None:
            raise ModuleNotFoundError(
                "sqlalchemy is required to access persistence models"
            )

    Base = _MissingBase()

try:  # pragma: no cover - same rationale as above
    from .sqlite import dispose_sqlite_engine
except ModuleNotFoundError:  # pragma: no cover - fallback when SQLAlchemy missing
    def dispose_sqlite_engine(*_args, **_kwargs) -> None:  # type: ignore[no-redef]
        return None

__all__ = ["Base", "dispose_sqlite_engine", "BaseRepository"]
