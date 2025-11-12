"""Tests for the application database facade."""
from __future__ import annotations

from contextlib import closing

from sqlalchemy import text

from theo.application.facades import database as facades_database


def _reset_database_state() -> None:
    facades_database._engine = None
    facades_database._SessionLocal = None
    facades_database._engine_url_override = None


def test_database_facade_configures_engine_and_sessions() -> None:
    """The database facade should manage the engine and session lifecycle."""

    _reset_database_state()
    engine = facades_database.configure_engine("sqlite:///:memory:")
    try:
        assert str(engine.url) == "sqlite:///:memory:"
        assert facades_database.get_engine() is engine

        session_gen = facades_database.get_session()
        with closing(next(session_gen)) as session:
            result = session.execute(text("SELECT 1")).scalar_one()
            assert result == 1
    finally:
        engine.dispose()
        _reset_database_state()
