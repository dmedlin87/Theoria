"""Unit tests for helper utilities in ``theo.cli``."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, List
import importlib.machinery as importlib_machinery
import sys
import types

if "fastapi" not in sys.modules:
    fastapi_stub = types.ModuleType("fastapi")
    fastapi_stub.status = types.SimpleNamespace()
    sys.modules["fastapi"] = fastapi_stub

if "sqlalchemy" not in sys.modules:
    sqlalchemy_stub = types.ModuleType("sqlalchemy")

    sqlalchemy_stub.__path__ = []  # pragma: no cover - mark as package
    sqlalchemy_spec = importlib_machinery.ModuleSpec("sqlalchemy", loader=None)
    sqlalchemy_spec.submodule_search_locations = []
    sqlalchemy_stub.__spec__ = sqlalchemy_spec

    class _FuncProxy:
        def __getattr__(self, name: str) -> Any:  # pragma: no cover - defensive
            raise NotImplementedError(f"sqlalchemy.func placeholder accessed for '{name}'")

    def _raise(*_args: object, **_kwargs: object) -> None:  # pragma: no cover
        raise NotImplementedError("sqlalchemy placeholder accessed")

    sqlalchemy_stub.func = _FuncProxy()
    sqlalchemy_stub.select = _raise
    sqlalchemy_stub.create_engine = _raise
    sqlalchemy_stub.text = lambda statement: statement

    exc_module = types.ModuleType("sqlalchemy.exc")

    class SQLAlchemyError(Exception):
        pass

    exc_module.SQLAlchemyError = SQLAlchemyError

    orm_module = types.ModuleType("sqlalchemy.orm")

    class Session:  # pragma: no cover - placeholder
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise NotImplementedError("sqlalchemy.orm.Session placeholder accessed")

    orm_module.Session = Session

    engine_module = types.ModuleType("sqlalchemy.engine")

    class Engine:  # pragma: no cover - placeholder
        pass

    engine_module.Engine = Engine

    ext_module = types.ModuleType("sqlalchemy.ext")
    ext_module.__path__ = []  # pragma: no cover - mark as package
    ext_spec = importlib_machinery.ModuleSpec("sqlalchemy.ext", loader=None)
    ext_spec.submodule_search_locations = []
    ext_module.__spec__ = ext_spec
    hybrid_module = types.ModuleType("sqlalchemy.ext.hybrid")

    def hybrid_property(func: Any | None = None, **_kwargs: object):  # pragma: no cover - stub
        if func is None:
            return hybrid_property
        return func

    hybrid_module.hybrid_property = hybrid_property
    ext_module.hybrid = hybrid_module

    sql_module = types.ModuleType("sqlalchemy.sql")
    sql_module.__path__ = []  # pragma: no cover - mark as package
    sql_spec = importlib_machinery.ModuleSpec("sqlalchemy.sql", loader=None)
    sql_spec.submodule_search_locations = []
    sql_module.__spec__ = sql_spec
    elements_module = types.ModuleType("sqlalchemy.sql.elements")
    elements_spec = importlib_machinery.ModuleSpec("sqlalchemy.sql.elements", loader=None)
    elements_spec.submodule_search_locations = []
    elements_module.__spec__ = elements_spec

    class ClauseElement:  # pragma: no cover - placeholder
        pass

    elements_module.ClauseElement = ClauseElement
    sql_module.elements = elements_module
    sqlalchemy_stub.sql = sql_module

    sys.modules["sqlalchemy"] = sqlalchemy_stub
    sys.modules["sqlalchemy.exc"] = exc_module
    sys.modules["sqlalchemy.orm"] = orm_module
    sys.modules["sqlalchemy.engine"] = engine_module
    sys.modules["sqlalchemy.ext"] = ext_module
    sys.modules["sqlalchemy.ext.hybrid"] = hybrid_module
    sys.modules["sqlalchemy.sql"] = sql_module
    sys.modules["sqlalchemy.sql.elements"] = elements_module

import click
import json
import time
import pytest

pytest.importorskip(
    "sqlalchemy",
    reason="CLI helper tests require SQLAlchemy; install optional dependency to run.",
)
from sqlalchemy.exc import SQLAlchemyError

from theo.commands.embedding_rebuild import _load_ids, _commit_with_retry
from theo.application.embeddings.checkpoint_store import (
    CheckpointError,
    EmbeddingCheckpoint,
    load_checkpoint,
    save_checkpoint,
)


class FakeSession:
    """Simple stand-in for :class:`sqlalchemy.orm.Session` used in tests."""

    def __init__(self, outcomes: Iterable[object]) -> None:
        self._events: List[object] = list(outcomes)
        self.commit_calls = 0
        self.rollback_calls = 0

    def commit(self) -> None:
        self.commit_calls += 1
        if self._events:
            event = self._events.pop(0)
            if isinstance(event, Exception):
                raise event
        # Successful commit when no events remain or when the next event is not an exception.

    def rollback(self) -> None:
        self.rollback_calls += 1


def test_load_ids_deduplicates_and_strips(tmp_path: Path) -> None:
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text(" id-1 \n\nid-2\nid-1\n id-3 \n", encoding="utf-8")

    result = _load_ids(ids_file)

    assert result == ["id-1", "id-2", "id-3"]


def test_read_checkpoint_handles_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"

    assert load_checkpoint(missing) is None


def test_read_checkpoint_raises_on_invalid_json(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text("not json", encoding="utf-8")

    assert load_checkpoint(checkpoint) is None
    with pytest.raises(CheckpointError):
        load_checkpoint(checkpoint, strict=True)


def test_read_checkpoint_handles_non_mapping_payload(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text("[]", encoding="utf-8")

    assert load_checkpoint(checkpoint) is None


def test_read_checkpoint_returns_checkpoint(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    state = EmbeddingCheckpoint.build(
        processed=3,
        total=5,
        last_id="p3",
        metadata={"resume": True},
    )
    save_checkpoint(checkpoint, state)

    result = load_checkpoint(checkpoint)
    assert isinstance(result, EmbeddingCheckpoint)
    assert result == state


def test_write_checkpoint_creates_expected_payload(tmp_path: Path) -> None:
    checkpoint = tmp_path / "nested" / "checkpoint.json"
    state = EmbeddingCheckpoint.build(
        processed=5,
        total=12,
        last_id="passage-42",
        metadata={"fast": True},
    )
    save_checkpoint(checkpoint, state)

    data = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert data["processed"] == 5
    assert data["total"] == 12
    assert data["last_id"] == "passage-42"
    assert data["metadata"] == {"fast": True}
    assert data["created_at"] == state.created_at.isoformat()
    assert data["updated_at"] == state.updated_at.isoformat()
    parsed_created_at = datetime.fromisoformat(data["created_at"])
    parsed_updated_at = datetime.fromisoformat(data["updated_at"])
    assert parsed_created_at.tzinfo is not None
    assert parsed_updated_at.tzinfo is not None
    assert parsed_created_at <= parsed_updated_at


def test_read_checkpoint_requires_timestamps(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(
        json.dumps(
            {
                "processed": 2,
                "total": 3,
                "last_id": "p2",
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )

    assert load_checkpoint(checkpoint) is None
    with pytest.raises(CheckpointError):
        load_checkpoint(checkpoint, strict=True)


def test_write_checkpoint_preserves_created_timestamp(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    first = cli._write_checkpoint(
        checkpoint,
        processed=1,
        total=2,
        last_id="p1",
        metadata={},
    )

    second = cli._write_checkpoint(
        checkpoint,
        processed=2,
        total=2,
        last_id="p2",
        metadata={},
        previous=first,
    )

    assert second.created_at == first.created_at
    assert second.updated_at >= first.updated_at


def test_read_checkpoint_rejects_invalid_counts(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(
        json.dumps(
            {
                "processed": 5,
                "total": 3,
                "last_id": "p5",
                "metadata": {},
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )

    assert load_checkpoint(checkpoint) is None
    with pytest.raises(CheckpointError):
        load_checkpoint(checkpoint, strict=True)


def test_normalise_timestamp_with_naive_datetime() -> None:
    naive = datetime(2024, 1, 2, 3, 4, 5)

    normalised = _normalise_timestamp(naive)

    assert normalised is not None
    assert normalised.tzinfo == timezone.utc
    assert normalised.replace(tzinfo=None) == naive


def test_normalise_timestamp_with_aware_datetime() -> None:
    aware = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=-5)))

    normalised = _normalise_timestamp(aware)

    expected = aware.astimezone(timezone.utc)
    assert normalised == expected


def test_commit_with_retry_succeeds_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession([None])
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda duration: sleeps.append(duration))

    duration = _commit_with_retry(session)

    assert session.commit_calls == 1
    assert session.rollback_calls == 0
    assert sleeps == []
    assert duration >= 0


def test_commit_with_retry_retries_and_eventually_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession([SQLAlchemyError("boom"), None])
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda duration: sleeps.append(duration))

    duration = _commit_with_retry(session)

    assert session.commit_calls == 2
    assert session.rollback_calls == 1
    assert sleeps == [pytest.approx(0.5)]
    assert duration >= 0


def test_commit_with_retry_raises_after_max_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession([SQLAlchemyError("boom"), SQLAlchemyError("boom again")])
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda duration: sleeps.append(duration))

    with pytest.raises(click.ClickException) as excinfo:
        _commit_with_retry(session, max_attempts=2)

    assert "2 attempt(s)" in str(excinfo.value)
    assert session.commit_calls == 2
    assert session.rollback_calls == 2
    assert sleeps == [pytest.approx(0.5)]


def test_commit_with_retry_propagates_non_sqlalchemy_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class UnexpectedError(Exception):
        pass

    session = FakeSession([UnexpectedError("unexpected")])
    monkeypatch.setattr(time, "sleep", lambda duration: None)

    with pytest.raises(UnexpectedError):
        _commit_with_retry(session)

    assert session.rollback_calls == 0
    assert session.commit_calls == 1

