from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import json
import pytest
from click import ClickException

pytest.importorskip("sqlalchemy")
from sqlalchemy.exc import SQLAlchemyError

from theo.checkpoints import CURRENT_EMBEDDING_CHECKPOINT_VERSION
from theo.cli import (
    _batched,
    _commit_with_retry,
    _load_ids,
    _normalise_timestamp,
    _read_checkpoint,
    _write_checkpoint,
)


class _FlakySession:
    def __init__(self, failures: int) -> None:
        self._remaining_failures = failures
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        if self._remaining_failures:
            self._remaining_failures -= 1
            raise SQLAlchemyError("transient failure")
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_batched_yields_chunks() -> None:
    iterator = iter(range(10))
    batches = list(_batched(iterator, 3))
    assert batches == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]


def test_batched_handles_empty_iterable() -> None:
    assert list(_batched(iter(()), 5)) == []


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
    actual = _normalise_timestamp(value)
    assert actual == expected


def test_load_ids_strips_and_deduplicates(tmp_path: Path) -> None:
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text(" a \nA\nb\n\nB\n", encoding="utf-8")
    assert _load_ids(ids_file) == ["a", "A", "b", "B"]


def test_read_checkpoint_handles_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.json"
    assert _read_checkpoint(missing_path) is None


def test_read_checkpoint_raises_on_invalid_json(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("not-json", encoding="utf-8")
    assert _read_checkpoint(invalid_path) is None

    with pytest.raises(json.JSONDecodeError):
        _read_checkpoint(invalid_path, raise_on_error=True)


def test_read_checkpoint_handles_non_mapping_payload(tmp_path: Path) -> None:
    wrong_type_path = tmp_path / "wrong.json"
    wrong_type_path.write_text("[]", encoding="utf-8")
    assert _read_checkpoint(wrong_type_path) is None


def test_write_checkpoint_roundtrip(tmp_path: Path) -> None:
    checkpoint = tmp_path / "state/checkpoint.json"
    metadata = {"flag": True}
    checkpoint_state = _write_checkpoint(
        checkpoint,
        processed=5,
        total=9,
        last_id="p5",
        metadata=metadata,
    )

    data = _read_checkpoint(checkpoint)
    assert data is not None
    assert data.processed == 5
    assert data.total == 9
    assert data.last_id == "p5"
    assert data.metadata == metadata
    assert data.created_at.tzinfo == timezone.utc
    assert data.updated_at.tzinfo == timezone.utc
    assert data.version == CURRENT_EMBEDDING_CHECKPOINT_VERSION


@pytest.mark.parametrize("failures", [0, 1, 2])
def test_commit_with_retry_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch, failures: int) -> None:
    session = _FlakySession(failures)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    duration = _commit_with_retry(session, max_attempts=3, backoff=0)
    assert session.commits == 1
    assert session.rollbacks == failures
    assert duration >= 0


def test_commit_with_retry_raises_after_exhausting_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FlakySession(failures=3)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    with pytest.raises(ClickException) as excinfo:
        _commit_with_retry(session, max_attempts=3, backoff=0)
    assert "Database commit failed" in str(excinfo.value)
    assert session.rollbacks == 3
