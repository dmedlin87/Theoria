"""Performance regression checks for watchlist analytics queries."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.application.facades import database as database_module
from theo.application.facades.database import Base, configure_engine, get_engine
from theo.services.api.app.db.models import Document, WatchlistEvent


def _initialise_database(db_path: Path) -> tuple[Session, Engine]:
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return Session(engine), engine


def test_document_window_query_uses_created_at_index(tmp_path: Path) -> None:
    session, engine = _initialise_database(tmp_path / "watchlist_perf.db")
    try:
        now = datetime.now(UTC)
        documents = [
            Document(title=f"Doc {i}", created_at=now - timedelta(days=i))
            for i in range(512)
        ]
        session.add_all(documents)
        session.commit()

        window_start = (now - timedelta(days=30)).isoformat()
        plan_rows = session.execute(
            text(
                "EXPLAIN QUERY PLAN "
                "SELECT id, created_at FROM documents "
                "WHERE created_at >= :window_start "
                "ORDER BY created_at DESC"
            ),
            {"window_start": window_start},
        ).all()
        detail = " \n".join(str(row[-1]) for row in plan_rows)

        assert "USING INDEX IX_DOCUMENTS_CREATED_AT" in detail.upper()
        assert "SCAN documents" not in detail
    finally:
        session.close()
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]


def test_watchlist_event_query_uses_run_started_index(tmp_path: Path) -> None:
    session, engine = _initialise_database(tmp_path / "watchlist_events_perf.db")
    try:
        base_time = datetime.now(UTC)
        events = [
            WatchlistEvent(
                watchlist_id="watchlist-1",
                run_started=base_time - timedelta(hours=i),
                run_completed=base_time - timedelta(hours=i - 1),
            )
            for i in range(1024)
        ]
        # Add a few rows for a different watchlist to confirm partition pruning.
        events.extend(
            WatchlistEvent(
                watchlist_id="watchlist-2",
                run_started=base_time - timedelta(hours=i),
                run_completed=base_time - timedelta(hours=i - 1),
            )
            for i in range(128)
        )
        session.add_all(events)
        session.commit()

        since = (base_time - timedelta(hours=24)).isoformat()
        plan_rows = session.execute(
            text(
                "EXPLAIN QUERY PLAN "
                "SELECT id, run_started FROM watchlist_events "
                "WHERE watchlist_id = :watchlist_id "
                "AND run_started >= :since "
                "ORDER BY run_started DESC"
            ),
            {"watchlist_id": "watchlist-1", "since": since},
        ).all()
        detail = " \n".join(str(row[-1]) for row in plan_rows)

        assert "USING INDEX IX_WATCHLIST_EVENTS_WATCHLIST_ID_RUN_STARTED" in detail.upper()
        assert "SCAN watchlist_events" not in detail
    finally:
        session.close()
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]
