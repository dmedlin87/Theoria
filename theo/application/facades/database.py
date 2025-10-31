"""Database utilities exposed via the application facade."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError
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

if os.name == "nt" and not getattr(Path, "__theo_unlink_retry__", False):
    _original_unlink = Path.unlink

    def _unlink_with_retry(self: Path, *args, **kwargs):  # type: ignore[override]
        attempts = 200
        delay = 0.05
        import gc

        for index in range(attempts):
            try:
                return _original_unlink(self, *args, **kwargs)
            except PermissionError:
                if index == attempts - 1:
                    raise
                gc.collect()
                time.sleep(delay)

    Path.unlink = _unlink_with_retry  # type: ignore[assignment]
    Path.__theo_unlink_retry__ = True  # type: ignore[attr-defined]

from theo.adapters.persistence import Base, dispose_sqlite_engine
from theo.application.facades.settings import get_settings

__all__ = ["Base", "configure_engine", "get_engine", "get_session"]

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None
_engine_url_override: str | None = None
_LOGGER = logging.getLogger(__name__)


def _is_sqlite_closed_database_error(exc: ProgrammingError) -> bool:
    """Return ``True`` if the error indicates SQLite was already closed."""

    # ``ProgrammingError`` from SQLAlchemy wraps the DB-API error in ``orig``.
    dbapi_exc = getattr(exc, "orig", None)

    sqlite_closed_indicators = (
        "closed database",
        "database is closed",
        "cannot operate on a closed database",
    )

    error_msg = str(dbapi_exc or exc).lower()
    matches_closed_indicators = any(
        indicator in error_msg for indicator in sqlite_closed_indicators
    )

    if sqlite3 is not None and isinstance(dbapi_exc, sqlite3.ProgrammingError):
        # Python 3.11 exposes ``sqlite_errorcode`` which is ``SQLITE_MISUSE``
        # when operations are attempted on a closed connection. Prefer the
        # error code when available but still confirm the message indicates a
        # closed database to avoid hiding unrelated misuse errors.
        error_code = getattr(dbapi_exc, "sqlite_errorcode", None)
        if error_code == sqlite3.SQLITE_MISUSE and matches_closed_indicators:
            return True

    return matches_closed_indicators
    """Check if ProgrammingError indicates a closed SQLite database.
    
    Uses multiple patterns to detect SQLite database closed errors across
    different SQLAlchemy versions and database drivers.
    """
    error_msg = str(exc).lower()
    
    # Common SQLite "database is closed" error patterns
    sqlite_closed_indicators = [
        "closed database",
        "database is closed", 
        "cannot operate on a closed database",
        "database disk image is malformed",  # Sometimes appears with closed DBs
        "sql logic error",  # Generic SQLite error that can indicate closure
    ]
    
    # Check if any indicator matches
    for indicator in sqlite_closed_indicators:
        if indicator in error_msg:
            return True
            
    # Additional check for SQLite-specific error patterns
    if "sqlite" in error_msg and ("closed" in error_msg or "disconnect" in error_msg):
        return True
        
    return False


class _TheoSession(Session):
    """Session subclass that aggressively releases SQLite handles on close."""

    def close(self) -> None:  # type: ignore[override]
        bind: Engine | None = None
        try:
            bind = self.get_bind()
        except Exception:
            bind = None
            
        try:
            super().close()
        except ProgrammingError as exc:
            # Use robust error detection instead of fragile string matching
            if not _is_sqlite_closed_database_error(exc):
                # Log the unexpected error for debugging but still raise it
                _LOGGER.warning(
                    "Unexpected ProgrammingError during session close: %s", 
                    exc, exc_info=True
                )
                raise
            
            # This is a known SQLite closed database error - safe to suppress
            _LOGGER.debug(
                "Suppressing expected SQLite closed database error during session close: %s", 
                exc
            )
            # SQLite disposal helpers may close the underlying connection
            # before SQLAlchemy attempts its implicit rollback. Suppress the
            # resulting noise so session cleanup remains idempotent.
            
        if bind is not None:
            dispose_sqlite_engine(bind, dispose_engine=False)


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
    engine = create_engine(database_url, **engine_kwargs)
    if database_url.startswith("sqlite") and not getattr(
        engine, "__theo_dispose_wrapped__", False
    ):
        original_dispose = engine.dispose

        def _wrapped_dispose(*args, **kwargs):
            def _call_original():
                original_dispose(*args, **kwargs)

            dispose_sqlite_engine(
                engine,
                dispose_engine=True,
                dispose_callable=_call_original,
            )

        engine.dispose = _wrapped_dispose  # type: ignore[assignment]
        engine.__theo_dispose_wrapped__ = True  # type: ignore[attr-defined]
    return engine


def configure_engine(database_url: str | None = None) -> Engine:
    """Create (or recreate) the global SQLAlchemy engine."""

    global _engine, _SessionLocal, _engine_url_override

    if database_url is None:
        database_url = get_settings().database_url
    else:
        _engine_url_override = database_url

    # Track the last explicit database URL so subsequent calls to ``get_engine``
    # can reuse it even after the engine has been disposed (e.g. during
    # application shutdown).
    _engine_url_override = database_url

    if _engine is not None:
        _engine.dispose()

    _engine = _create_engine(database_url)
    _SessionLocal = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
        class_=_TheoSession,
    )
    return _engine


def get_engine() -> Engine:
    """Return the configured SQLAlchemy engine, creating it on demand."""

    global _engine, _engine_url_override
    if _engine is None:
        database_url = _engine_url_override or get_settings().database_url
        _engine = configure_engine(database_url)
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
