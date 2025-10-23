"""Utilities for triggering discovery generation in background tasks."""

from __future__ import annotations

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session, sessionmaker

from theo.adapters.persistence.discovery_repository import SQLAlchemyDiscoveryRepository
from theo.adapters.persistence.document_repository import SQLAlchemyDocumentRepository
from theo.application.facades.database import get_engine

from .service import DiscoveryService

_SESSION_FACTORY: sessionmaker[Session] | None = None


def _get_session_factory() -> sessionmaker[Session]:
    global _SESSION_FACTORY
    if _SESSION_FACTORY is None:
        engine = get_engine()
        _SESSION_FACTORY = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _SESSION_FACTORY


def run_discovery_refresh(user_id: str) -> None:
    """Execute discovery generation for *user_id* within a fresh session."""

    factory = _get_session_factory()
    with factory() as session:
        discovery_repo = SQLAlchemyDiscoveryRepository(session)
        document_repo = SQLAlchemyDocumentRepository(session)
        service = DiscoveryService(discovery_repo, document_repo)
        try:
            service.refresh_user_discoveries(user_id)
            session.commit()
        except Exception:
            session.rollback()
            raise


def schedule_discovery_refresh(
    background_tasks: BackgroundTasks, user_id: str | None
) -> None:
    """Queue discovery refresh work if a *user_id* is available."""

    if not user_id:
        return
    background_tasks.add_task(run_discovery_refresh, user_id)


__all__ = ["run_discovery_refresh", "schedule_discovery_refresh"]
