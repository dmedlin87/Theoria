"""Shared SQLAlchemy repository helpers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from sqlalchemy.orm import Session


if TYPE_CHECKING:  # pragma: no cover - only needed for type checkers
    from sqlalchemy.sql import Executable, Select
    from sqlalchemy.engine import Result, ScalarResult
else:  # pragma: no cover - runtime fallback for SQLAlchemy < 1.4
    Result = ScalarResult = Any  # type: ignore[misc,assignment]
    Executable = Select = Any  # type: ignore[misc,assignment]


ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    """Base repository coordinating access to a SQLAlchemy session."""

    def __init__(self, session: Session):
        self._session = session

    @property
    def session(self) -> Session:
        """Return the active SQLAlchemy session."""

        return self._session

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------
    def add(self, instance: ModelT) -> ModelT:
        """Register *instance* with the current session."""

        self._session.add(instance)
        return instance

    def add_all(self, instances: Iterable[ModelT]) -> list[ModelT]:
        """Register *instances* with the session, returning a concrete list."""

        payload = list(instances)
        if payload:
            self._session.add_all(payload)
        return payload

    def delete(self, instance: ModelT) -> None:
        """Schedule *instance* for deletion."""

        self._session.delete(instance)

    def flush(self) -> None:
        """Flush pending changes to the database."""

        self._session.flush()

    def refresh(self, instance: ModelT) -> None:
        """Refresh *instance* state from the database."""

        self._session.refresh(instance)

    def get(self, model: type[ModelT], ident: Any) -> ModelT | None:
        """Retrieve an entity by primary key."""

        return self._session.get(model, ident)

    def execute(self, statement: Executable) -> Result[Any]:
        """Execute a SQL expression against the session bind."""

        return self._session.execute(statement)

    # ------------------------------------------------------------------
    # Convenience wrappers around ``Session.scalars``
    # ------------------------------------------------------------------
    def scalars(self, statement: Select[Any]) -> ScalarResult[Any]:
        """Return a scalar result for *statement*."""

        return self._session.scalars(statement)

    def scalar_first(self, statement: Select[Any]) -> Any | None:
        """Return the first scalar for *statement*, if present."""

        return self.scalars(statement).first()

    def scalar_one_or_none(self, statement: Select[Any]) -> Any | None:
        """Return exactly one scalar for *statement* or ``None``."""

        return self.scalars(statement).one_or_none()

    def scalar_all(self, statement: Select[Any]) -> list[Any]:
        """Return all scalar rows for *statement* as a list."""

        return list(self.scalars(statement))


__all__ = ["BaseRepository"]

