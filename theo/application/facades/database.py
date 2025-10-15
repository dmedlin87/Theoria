"""Database utilities exposed via the application facade."""

from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

try:  # pragma: no cover - optional sqlite context cleanup shim
    import sqlite3
except Exception:  # pragma: no cover - non-sqlite environments
    sqlite3 = None  # type: ignore
else:
    if not getattr(sqlite3, "__theo_closing_patch__", False):
        _original_sqlite_connect = sqlite3.connect

        class _TheoClosingConnection(sqlite3.Connection):  # type: ignore[misc]
            def __exit__(self, exc_type, exc, tb):  # type: ignore[override]
                result = super().__exit__(exc_type, exc, tb)
                try:
                    super().close()
                except Exception:
                    pass
                return result

        def _connect_with_closing(*args, **kwargs):
            if "factory" not in kwargs:
                kwargs["factory"] = _TheoClosingConnection
            return _original_sqlite_connect(*args, **kwargs)

        sqlite3.connect = _connect_with_closing  # type: ignore[assignment]
        sqlite3.__theo_closing_patch__ = True  # type: ignore[attr-defined]

from theo.application.facades.settings import get_settings
from theo.services.api.app.db.models import Base

__all__ = ["Base", "configure_engine", "get_engine", "get_session"]

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _create_engine(database_url: str) -> Engine:
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False, "timeout": 30}
    engine_kwargs: dict[str, object] = {
        "future": True,
        "echo": False,
        "connect_args": connect_args,
    }
    if database_url.startswith("sqlite"):
        engine_kwargs["poolclass"] = NullPool
    return create_engine(database_url, **engine_kwargs)


def configure_engine(database_url: str | None = None) -> Engine:
    """Create (or recreate) the global SQLAlchemy engine."""

    global _engine, _SessionLocal

    if database_url is None:
        database_url = get_settings().database_url

    if _engine is not None:
        _engine.dispose()

    _engine = _create_engine(database_url)
    _SessionLocal = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )
    return _engine


def get_engine() -> Engine:
    """Return the configured SQLAlchemy engine, creating it on demand."""

    global _engine
    if _engine is None:
        _engine = configure_engine(get_settings().database_url)
    return _engine


def get_session() -> Generator[Session, None, None]:
    """Yield a database session for request handling."""

    global _SessionLocal
    if _SessionLocal is None:
        configure_engine(get_settings().database_url)
    assert _SessionLocal is not None  # for type checkers
    session: Session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
