"""Database utilities and SQLAlchemy session management."""

from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .settings import get_settings

Base = declarative_base()

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _create_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, future=True, echo=False, connect_args=connect_args)


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


# Ensure the engine is created when the module is imported so that metadata operations
# (e.g., Base.metadata.create_all) work during application startup.
get_engine()
