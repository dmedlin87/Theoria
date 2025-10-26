"""Unit tests for helper utilities in ``theo.cli``."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List

import click
import json
import pytest
from sqlalchemy.exc import SQLAlchemyError

from theo import cli


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

    result = cli._load_ids(ids_file)

    assert result == ["id-1", "id-2", "id-3"]


def test_read_checkpoint_handles_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"

    assert cli._read_checkpoint(missing) == {}


def test_read_checkpoint_raises_on_invalid_json(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text("not json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        cli._read_checkpoint(checkpoint)


def test_read_checkpoint_handles_non_mapping_payload(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text("[]", encoding="utf-8")

    assert cli._read_checkpoint(checkpoint) == {}


def test_read_checkpoint_returns_dict(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(json.dumps({"processed": 3}), encoding="utf-8")

    assert cli._read_checkpoint(checkpoint) == {"processed": 3}


def test_write_checkpoint_creates_expected_payload(tmp_path: Path) -> None:
    checkpoint = tmp_path / "nested" / "checkpoint.json"

    cli._write_checkpoint(
        checkpoint,
        processed=5,
        total=12,
        last_id="passage-42",
        metadata={"fast": True},
    )

    data = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert data["processed"] == 5
    assert data["total"] == 12
    assert data["last_id"] == "passage-42"
    assert data["metadata"] == {"fast": True}
    # Ensure ``updated_at`` is an ISO formatted timestamp with timezone information.
    parsed_updated_at = datetime.fromisoformat(data["updated_at"])
    assert parsed_updated_at.tzinfo is not None


def test_normalise_timestamp_with_naive_datetime() -> None:
    naive = datetime(2024, 1, 2, 3, 4, 5)

    normalised = cli._normalise_timestamp(naive)

    assert normalised is not None
    assert normalised.tzinfo == timezone.utc
    assert normalised.replace(tzinfo=None) == naive


def test_normalise_timestamp_with_aware_datetime() -> None:
    aware = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=-5)))

    normalised = cli._normalise_timestamp(aware)

    expected = aware.astimezone(timezone.utc)
    assert normalised == expected


def test_commit_with_retry_succeeds_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession([None])
    sleeps: list[float] = []
    monkeypatch.setattr(cli.time, "sleep", lambda duration: sleeps.append(duration))

    cli._commit_with_retry(session)

    assert session.commit_calls == 1
    assert session.rollback_calls == 0
    assert sleeps == []


def test_commit_with_retry_retries_and_eventually_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession([SQLAlchemyError("boom"), None])
    sleeps: list[float] = []
    monkeypatch.setattr(cli.time, "sleep", lambda duration: sleeps.append(duration))

    cli._commit_with_retry(session)

    assert session.commit_calls == 2
    assert session.rollback_calls == 1
    assert sleeps == [pytest.approx(0.5)]


def test_commit_with_retry_raises_after_max_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession([SQLAlchemyError("boom"), SQLAlchemyError("boom again")])
    sleeps: list[float] = []
    monkeypatch.setattr(cli.time, "sleep", lambda duration: sleeps.append(duration))

    with pytest.raises(click.ClickException) as excinfo:
        cli._commit_with_retry(session, max_attempts=2)

    assert "2 attempt(s)" in str(excinfo.value)
    assert session.commit_calls == 2
    assert session.rollback_calls == 2
    assert sleeps == [pytest.approx(0.5)]


def test_commit_with_retry_propagates_non_sqlalchemy_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class UnexpectedError(Exception):
        pass

    session = FakeSession([UnexpectedError("unexpected")])
    monkeypatch.setattr(cli.time, "sleep", lambda duration: None)

    with pytest.raises(UnexpectedError):
        cli._commit_with_retry(session)

    assert session.rollback_calls == 0
    assert session.commit_calls == 1

