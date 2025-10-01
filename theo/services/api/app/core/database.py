"""Database utilities and SQLAlchemy session management."""

from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from .settings import get_settings

Base = declarative_base()

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _create_engine(database_url: str) -> Engine:
    connect_args = (
        {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    )
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
    if _SessionLocal is None:  # pragma: no cover - configuration failed
        raise RuntimeError("Database engine is not configured")
    session: Session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
