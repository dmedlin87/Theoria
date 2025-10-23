"""Tests for helper utilities in :mod:`theo.cli`."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click
import pytest
from sqlalchemy.exc import SQLAlchemyError

from theo import cli


class DummySession:
    def __init__(self, *, fail_times: int = 0) -> None:
        self._fail_times = fail_times
        self.commit_calls = 0
        self.rollback_calls = 0

    def commit(self) -> None:
        self.commit_calls += 1
        if self._fail_times > 0:
            self._fail_times -= 1
            raise SQLAlchemyError("boom")

    def rollback(self) -> None:
        self.rollback_calls += 1


def test_load_ids_deduplicates_and_ignores_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "ids.txt"
    path.write_text("\n".join(["a", "", "b", "a", "c", "b", "  "]), encoding="utf-8")

    result = cli._load_ids(path)

    assert result == ["a", "b", "c"]


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, None),
        (datetime(2024, 1, 1, 12, 0), datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)),
        (
            datetime(2024, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=2))),
            datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
        ),
    ],
)
def test_normalise_timestamp(value: datetime | None, expected: datetime | None) -> None:
    assert cli._normalise_timestamp(value) == expected


def test_read_checkpoint_handles_missing_invalid_and_non_dict(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"

    # Missing file
    assert cli._read_checkpoint(path) == {}

    # Invalid JSON
    path.write_text("not json", encoding="utf-8")
    assert cli._read_checkpoint(path) == {}

    # Valid JSON but not a dict
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert cli._read_checkpoint(path) == {}

    # Valid dictionary payload
    payload = {"processed": 5}
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert cli._read_checkpoint(path) == payload


def test_write_checkpoint_serialises_expected_payload(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"

    metadata = {"fast": True}
    cli._write_checkpoint(
        path,
        processed=3,
        total=10,
        last_id="abc",
        metadata=metadata,
    )

    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["processed"] == 3
    assert data["total"] == 10
    assert data["last_id"] == "abc"
    assert data["metadata"] == metadata
    assert datetime.fromisoformat(data["updated_at"]).tzinfo == timezone.utc


def test_commit_with_retry_eventually_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    session = DummySession(fail_times=1)
    monkeypatch.setattr(cli.time, "sleep", lambda *_: None)

    cli._commit_with_retry(session, max_attempts=3, backoff=0)

    assert session.commit_calls == 2
    assert session.rollback_calls == 1


def test_commit_with_retry_raises_after_exhausting_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = DummySession(fail_times=5)
    monkeypatch.setattr(cli.time, "sleep", lambda *_: None)

    with pytest.raises(click.ClickException):
        cli._commit_with_retry(session, max_attempts=2, backoff=0)

    assert session.commit_calls == 2
    assert session.rollback_calls == 2
