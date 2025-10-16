"""Database utilities exposed via the application facade."""

from __future__ import annotations

import os
import time
from pathlib import Path
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

from theo.application.facades.settings import get_settings
from theo.services.api.app.db.models import Base
from theo.services.api.app.db.seeds import _dispose_sqlite_engine

__all__ = ["Base", "configure_engine", "get_engine", "get_session"]

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None
_engine_url_override: str | None = None


class _TheoSession(Session):
    """Session subclass that aggressively releases SQLite handles on close."""

    def close(self) -> None:  # type: ignore[override]
        bind: Engine | None = None
        try:
            bind = self.get_bind()
        except Exception:
            bind = None
        super().close()
        if bind is not None:
            _dispose_sqlite_engine(bind, dispose_engine=False)


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

            _dispose_sqlite_engine(
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
