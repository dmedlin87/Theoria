"""Unit tests for helper utilities in ``theo.infrastructure.api.app.db.seeds``."""

from __future__ import annotations

import sys
import types
from unittest.mock import Mock

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine
from sqlalchemy.orm import Session

from theo.infrastructure.api.app.db import seeds
from theo.adapters.persistence import sqlite as sqlite_utils


@pytest.fixture
def sqlite_engine():
    """Provide an in-memory SQLite engine for unit tests."""

    engine = create_engine("sqlite:///:memory:", future=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def patch_resource_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub expensive resource cleanup helpers invoked by ``_dispose_sqlite_engine``."""

    monkeypatch.setattr(sqlite_utils.gc, "get_objects", lambda: [])
    monkeypatch.setattr(sqlite_utils.gc, "collect", lambda: None)
    monkeypatch.setattr(sqlite_utils.time, "sleep", lambda *_args, **_kwargs: None)
    fake_inspect = types.SimpleNamespace(stack=lambda: [])
    monkeypatch.setitem(sys.modules, "inspect", fake_inspect)


def test_dispose_sqlite_engine_invokes_dispose_callable(
    sqlite_engine, patch_resource_cleanup
) -> None:
    dispose_mock = Mock()

    seeds._dispose_sqlite_engine(sqlite_engine, dispose_callable=dispose_mock)

    dispose_mock.assert_called_once_with()


def test_dispose_sqlite_engine_respects_disable_flag(
    sqlite_engine, patch_resource_cleanup
) -> None:
    dispose_mock = Mock()

    seeds._dispose_sqlite_engine(
        sqlite_engine,
        dispose_engine=False,
        dispose_callable=dispose_mock,
    )

    dispose_mock.assert_not_called()


def test_get_session_connection_returns_engine_connection(sqlite_engine) -> None:
    session = Session(sqlite_engine)
    try:
        connection, should_close = seeds._get_session_connection(session)
    finally:
        session.close()

    assert should_close is False
    assert connection is not None
    assert connection.engine is sqlite_engine


def test_table_exists_detects_existing_and_missing_tables(sqlite_engine) -> None:
    metadata = MetaData()
    Table("example", metadata, Column("id", Integer, primary_key=True))
    metadata.create_all(sqlite_engine)

    session = Session(sqlite_engine)
    try:
        assert seeds._table_exists(session, "example") is True
        assert seeds._table_exists(session, "missing") is False
    finally:
        session.close()


def test_table_has_column_handles_present_and_missing_columns(sqlite_engine) -> None:
    metadata = MetaData()
    Table("sample", metadata, Column("id", Integer, primary_key=True))
    metadata.create_all(sqlite_engine)

    session = Session(sqlite_engine)
    try:
        assert seeds._table_has_column(session, "sample", "id") is True
        assert seeds._table_has_column(session, "sample", "other") is False
    finally:
        session.close()
