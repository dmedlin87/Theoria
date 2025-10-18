"""Background scheduler for automatic discovery generation."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from theo.services.bootstrap import resolve_application

from theo.adapters.persistence.discovery_repository import SQLAlchemyDiscoveryRepository
from theo.adapters.persistence.document_repository import SQLAlchemyDocumentRepository
from theo.adapters.persistence.models import Document
from ..discoveries import DiscoveryService

logger = logging.getLogger(__name__)


_APPLICATION_CONTAINER, _ADAPTER_REGISTRY = resolve_application()
_SESSION_FACTORY: sessionmaker[Session] | None = None


def _get_session_factory() -> sessionmaker[Session]:
    """Lazily initialise and cache the session factory via platform bootstrap."""

    global _SESSION_FACTORY
    if _SESSION_FACTORY is None:
        engine = _ADAPTER_REGISTRY.resolve("engine")
        _SESSION_FACTORY = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _SESSION_FACTORY


class DiscoveryScheduler:
    """Manages background discovery generation tasks."""

    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone="UTC")
        self._running = False

    def start(self):
        """Start the background scheduler."""
        if self._running:
            logger.warning("Discovery scheduler already running")
            return

        # Run discovery refresh every 30 minutes
        self.scheduler.add_job(
            func=self._refresh_all_users,
            trigger=IntervalTrigger(minutes=30),
            id="discovery_refresh",
            name="Refresh discoveries for all users",
            replace_existing=True,
        )

        self.scheduler.start()
        self._running = True
        logger.info("Discovery scheduler started")

    def stop(self):
        """Stop the background scheduler."""
        if not self._running:
            return

        self.scheduler.shutdown(wait=True)
        self._running = False
        logger.info("Discovery scheduler stopped")

    def trigger_user_refresh(self, session: Session, user_id: str):
        """Immediately trigger discovery refresh for a specific user."""
        try:
            logger.info(f"Triggering discovery refresh for user {user_id}")
            discovery_repo = SQLAlchemyDiscoveryRepository(session)
            document_repo = SQLAlchemyDocumentRepository(session)
            service = DiscoveryService(discovery_repo, document_repo)
            discoveries = service.refresh_user_discoveries(user_id)
            session.commit()
            logger.info(f"Generated {len(discoveries)} discoveries for user {user_id}")
            return discoveries
        except Exception as exc:
            logger.exception(f"Failed to refresh discoveries for user {user_id}: {exc}")
            session.rollback()
            return []

    def _refresh_all_users(self):
        """Background task to refresh discoveries for all active users."""
        session_factory = _get_session_factory()
        session = session_factory()

        try:
            # Find users with recent document activity (last 7 days)
            cutoff = datetime.now(UTC) - timedelta(days=7)
            stmt = (
                select(Document.collection)
                .where(Document.created_at >= cutoff)
                .distinct()
            )
            active_users = list(session.scalars(stmt))

            logger.info(f"Refreshing discoveries for {len(active_users)} active users")

            for user_id in active_users:
                if not user_id:
                    continue
                try:
                    # Reuse session for all users in batch
                    self.trigger_user_refresh(session, user_id)
                except Exception as exc:
                    logger.exception(f"Failed to refresh user {user_id}: {exc}")
                    # Continue with next user after error
                    continue

            logger.info("Discovery refresh completed for all users")

        except Exception as exc:
            logger.exception(f"Discovery refresh task failed: {exc}")
            session.rollback()
        finally:
            session.close()


# Global scheduler instance
_scheduler: DiscoveryScheduler | None = None


def get_scheduler() -> DiscoveryScheduler:
    """Get or create the global discovery scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = DiscoveryScheduler()
    return _scheduler


def start_discovery_scheduler():
    """Start the global discovery scheduler."""
    scheduler = get_scheduler()
    scheduler.start()


def stop_discovery_scheduler():
    """Stop the global discovery scheduler."""
    scheduler = get_scheduler()
    scheduler.stop()


__all__ = [
    "DiscoveryScheduler",
    "get_scheduler",
    "start_discovery_scheduler",
    "stop_discovery_scheduler",
]
