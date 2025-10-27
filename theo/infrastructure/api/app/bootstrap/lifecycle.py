"""Application lifespan management for the API service."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

SQLALCHEMY_AVAILABLE = True
try:  # pragma: no cover - optional dependency bridge
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session
except ImportError:  # pragma: no cover - fallback when SQLAlchemy missing
    SQLALCHEMY_AVAILABLE = False

    class OperationalError(RuntimeError):
        """Fallback operational error when SQLAlchemy is unavailable."""

    class Session:  # type: ignore[too-many-ancestors]
        """Fallback session stub when SQLAlchemy is unavailable."""

        def __init__(self, *_args, **_kwargs):  # type: ignore[unused-argument]
            raise OperationalError("SQLAlchemy is required for application startup tasks")

        def execute(self, *_args, **_kwargs):  # type: ignore[unused-argument]
            raise OperationalError("SQLAlchemy is required for application startup tasks")

try:  # pragma: no cover - optional dependency bridge
    from ..db.run_sql_migrations import run_sql_migrations as _run_sql_migrations
except Exception:  # pragma: no cover - fallback for tests / optional deps

    def _run_sql_migrations(*_args, **_kwargs):  # type: ignore[unused-argument]
        raise OperationalError("Database migrations are unavailable without SQLAlchemy")

try:  # pragma: no cover - optional dependency bridge
    from ..db.seeds import seed_reference_data as _seed_reference_data
except Exception:  # pragma: no cover - fallback for tests / optional deps

    def _seed_reference_data(*_args, **_kwargs):  # type: ignore[unused-argument]
        raise OperationalError("Database seeds are unavailable without SQLAlchemy")


run_sql_migrations = _run_sql_migrations
seed_reference_data = _seed_reference_data

from theo.application.facades import database as database_module
from theo.application.facades.database import Base, get_engine


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Perform startup and shutdown tasks for the FastAPI application."""

    engine = get_engine()
    discovery_scheduler = None

    try:
        if SQLALCHEMY_AVAILABLE:
            Base.metadata.create_all(bind=engine)
            try:
                run_sql_migrations(engine)
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.warning("Failed to run SQL migrations during startup", exc_info=exc)
            with Session(engine) as session:
                try:
                    seed_reference_data(session)
                except OperationalError as exc:  # pragma: no cover - defensive startup guard
                    session.rollback()
                    logger.warning(
                        "Skipping reference data seeding due to database error", exc_info=exc
                    )

        # Start background discovery scheduler
        try:
            from ..workers.discovery_scheduler import start_discovery_scheduler

            start_discovery_scheduler()
            discovery_scheduler = True
            logger.info("Discovery scheduler started successfully")
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning("Failed to start discovery scheduler", exc_info=exc)

        yield
    finally:
        # Stop discovery scheduler
        if discovery_scheduler:
            try:
                from ..workers.discovery_scheduler import stop_discovery_scheduler

                stop_discovery_scheduler()
                logger.info("Discovery scheduler stopped")
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.debug("Error stopping discovery scheduler", exc_info=exc)

        try:
            engine.dispose()
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.debug("Error disposing database engine during shutdown", exc_info=exc)
        else:
            import gc as _gc
            import time as _time

            _gc.collect()
            _time.sleep(0.01)
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]
