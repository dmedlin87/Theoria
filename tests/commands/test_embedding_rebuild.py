from __future__ import annotations

import json
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
import click
from click.testing import CliRunner

if "fastapi" not in sys.modules:
    fastapi_stub = types.ModuleType("fastapi")
    fastapi_stub.status = types.SimpleNamespace()
    sys.modules["fastapi"] = fastapi_stub

if "pydantic" not in sys.modules:
    pydantic_stub = types.ModuleType("pydantic")

    class _BaseModel:
        def __init__(self, **_kwargs: object) -> None:  # pragma: no cover - simple stub
            pass

    def _identity_decorator(*_args: object, **_kwargs: object):
        def _decorator(func: Any) -> Any:
            return func

        return _decorator

    def _field(*_args: object, **_kwargs: object) -> None:
        return None

    pydantic_stub.BaseModel = _BaseModel
    pydantic_stub.Field = _field
    pydantic_stub.field_validator = _identity_decorator
    pydantic_stub.model_validator = _identity_decorator
    pydantic_stub.AliasChoices = type("AliasChoices", (), {})

    sys.modules["pydantic"] = pydantic_stub

embeddings_stub = types.ModuleType("theo.infrastructure.api.app.ingest.embeddings")


def _stub_clear_cache() -> None:
    return None


def _stub_get_service() -> Any:
    raise RuntimeError("embedding service stub should be patched")


def _stub_lexical_representation(*_args: object, **_kwargs: object) -> str:
    raise RuntimeError("lexical_representation stub should not be used at import time")


class _StubEmbeddingService:  # pragma: no cover - placeholder for discovery
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise RuntimeError("EmbeddingService stub should not be instantiated")


embeddings_stub.clear_embedding_cache = _stub_clear_cache
embeddings_stub.get_embedding_service = _stub_get_service
embeddings_stub.lexical_representation = _stub_lexical_representation
embeddings_stub.EmbeddingService = _StubEmbeddingService
from theo.application.facades.resilience import ResilienceError as _RealResilienceError

embeddings_stub.ResilienceError = _RealResilienceError
sys.modules["theo.infrastructure.api.app.ingest.embeddings"] = embeddings_stub

sanitizer_stub = types.ModuleType("theo.infrastructure.api.app.ingest.sanitizer")
sanitizer_stub.sanitize_passage_text = lambda text: text
sys.modules["theo.infrastructure.api.app.ingest.sanitizer"] = sanitizer_stub

pytest.importorskip("sqlalchemy")
from sqlalchemy.exc import SQLAlchemyError

from theo.application.embeddings import EmbeddingRebuildResult
from theo.checkpoints import CURRENT_EMBEDDING_CHECKPOINT_VERSION
from theo.commands import embedding_rebuild
from theo.commands.embedding_rebuild import (
    _batched,
    _commit_with_retry,
    _load_ids,
    _normalise_timestamp,
    _read_checkpoint,
    _write_checkpoint,
    rebuild_embeddings_cmd,
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


class _ExplodingSession:
    def commit(self) -> None:
        raise SQLAlchemyError("permanent failure")

    def rollback(self) -> None:
        self.rolled_back = True


def test_batched_yields_chunks() -> None:
    assert list(_batched(iter(range(7)), 3)) == [[0, 1, 2], [3, 4, 5], [6]]


def test_batched_rejects_non_positive_batch_size() -> None:
    with pytest.raises(ValueError):
        list(_batched(iter(range(3)), 0))


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
    assert _normalise_timestamp(value) == expected


def test_load_ids_strips_and_deduplicates(tmp_path: Path) -> None:
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text(" a \nA\nb\n\nB\n", encoding="utf-8")
    assert _load_ids(ids_file) == ["a", "A", "b", "B"]


def test_read_checkpoint_handles_missing(tmp_path: Path) -> None:
    assert _read_checkpoint(tmp_path / "missing.json") is None


def test_write_and_read_checkpoint_roundtrip(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint = _write_checkpoint(
        checkpoint_path,
        processed=3,
        total=10,
        last_id="p3",
        metadata={"mode": "fast"},
    )
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert payload["version"] == CURRENT_EMBEDDING_CHECKPOINT_VERSION
    assert checkpoint.processed == 3
    loaded = _read_checkpoint(checkpoint_path)
    assert loaded == checkpoint


def test_commit_with_retry_eventually_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FlakySession(failures=1)
    duration = _commit_with_retry(session, max_attempts=2, backoff=0)
    assert session.commits == 1
    assert session.rollbacks == 1
    assert duration >= 0


def test_commit_with_retry_raises_after_exhaustion() -> None:
    session = _ExplodingSession()
    with pytest.raises(click.ClickException):
        _commit_with_retry(session, max_attempts=1, backoff=0)


class _StubRegistry:
    def __init__(self, service: object, engine: object) -> None:
        self._service = service
        self._engine = engine
        self.resolved: list[str] = []

    def resolve(self, name: str) -> object:
        self.resolved.append(name)
        if name == "embedding_rebuild_service":
            return self._service
        if name == "engine":
            return self._engine
        raise KeyError(name)


class _StubEmbeddingService:
    def embed(self, texts: list[str], *, batch_size: int) -> list[list[float]]:
        return [[float(index)] for index, _ in enumerate(texts)]


class _StubConfig:
    def __init__(self, batch_size: int) -> None:
        self.initial_batch_size = batch_size
        self.commit_cadence = 2

    def compute_yield_size(self, batch_size: int) -> int:
        return batch_size

    @property
    def resource_probe(self) -> Any:
        return lambda: types.SimpleNamespace(load_avg_1m=None, memory_available=None)

    def adjust_batch_size(self, *, batch_size: int, duration: float, resource_snapshot: Any) -> int:
        return batch_size

    def to_metadata(self) -> dict[str, object]:
        return {"initial_batch_size": self.initial_batch_size}


class _RecordingService(embedding_rebuild.EmbeddingRebuildService):  # type: ignore[misc]
    def __init__(self, result: EmbeddingRebuildResult) -> None:
        self.result = result
        self.received_options: embedding_rebuild.EmbeddingRebuildOptions | None = None

    def rebuild_embeddings(  # type: ignore[override]
        self,
        options: embedding_rebuild.EmbeddingRebuildOptions,
        *,
        on_start: Any | None = None,
        on_progress: Any | None = None,
        checkpoint: Any | None = None,
    ) -> EmbeddingRebuildResult:
        self.received_options = options
        if on_start is not None:
            on_start(
                embedding_rebuild.EmbeddingRebuildStart(
                    total=0, missing_ids=[], skip_count=0
                )
            )
        return self.result


@pytest.fixture(autouse=True)
def _reset_telemetry_flag() -> None:
    embedding_rebuild._TELEMETRY_READY = False


def test_rebuild_embeddings_invokes_service_with_expected_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ids_path = tmp_path / "ids.txt"
    ids_path.write_text("a\na\nb\n", encoding="utf-8")

    service_result = EmbeddingRebuildResult(
        processed=0, total=0, duration=0.1, missing_ids=[], metadata={}
    )
    service = _RecordingService(service_result)
    registry = _StubRegistry(service, engine=object())

    monkeypatch.setattr(
        embedding_rebuild, "resolve_application", lambda: (registry._engine, registry)
    )
    monkeypatch.setattr(embedding_rebuild, "get_embedding_service", lambda: _StubEmbeddingService())
    cache_calls: list[bool] = []
    monkeypatch.setattr(embedding_rebuild, "clear_embedding_cache", lambda: cache_calls.append(True))
    monkeypatch.setattr(
        embedding_rebuild.EmbeddingRebuildConfig,
        "for_mode",
        classmethod(lambda cls, fast: _StubConfig(batch_size=32)),
    )
    embedding_rebuild._TELEMETRY_READY = True

    runner = CliRunner()
    result = runner.invoke(
        rebuild_embeddings_cmd,
        ["--fast", "--no-cache", "--ids-file", str(ids_path)],
    )

    assert result.exit_code == 0, result.output
    assert cache_calls == [True]
    assert isinstance(service.received_options, embedding_rebuild.EmbeddingRebuildOptions)
    assert service.received_options.fast is True
    assert service.received_options.clear_cache is True
    assert service.received_options.batch_size == 32
    assert service.received_options.ids == ["a", "b"]
    assert registry.resolved == ["embedding_rebuild_service", "engine"]


def test_rebuild_embeddings_handles_service_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailingService(embedding_rebuild.EmbeddingRebuildService):  # type: ignore[misc]
        def __init__(self) -> None:
            pass

        def rebuild_embeddings(self, *_args: Any, **_kwargs: Any) -> EmbeddingRebuildResult:
            raise embedding_rebuild.EmbeddingRebuildError("boom")

    service = _FailingService()
    registry = _StubRegistry(service, engine=object())
    monkeypatch.setattr(
        embedding_rebuild, "resolve_application", lambda: (registry._engine, registry)
    )
    monkeypatch.setattr(embedding_rebuild, "get_embedding_service", lambda: _StubEmbeddingService())
    monkeypatch.setattr(
        embedding_rebuild.EmbeddingRebuildConfig,
        "for_mode",
        classmethod(lambda cls, fast: _StubConfig(batch_size=16)),
    )
    embedding_rebuild._TELEMETRY_READY = True

    runner = CliRunner()
    result = runner.invoke(rebuild_embeddings_cmd, ["--fast"])
    assert result.exit_code == 1
    assert "boom" in result.output


def test_rebuild_embeddings_invalid_checkpoint_resume(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text("not-json", encoding="utf-8")

    service = _RecordingService(
        EmbeddingRebuildResult(processed=0, total=0, duration=0.1, missing_ids=[], metadata={})
    )
    registry = _StubRegistry(service, engine=object())
    monkeypatch.setattr(
        embedding_rebuild, "resolve_application", lambda: (registry._engine, registry)
    )
    monkeypatch.setattr(embedding_rebuild, "get_embedding_service", lambda: _StubEmbeddingService())
    monkeypatch.setattr(
        embedding_rebuild.EmbeddingRebuildConfig,
        "for_mode",
        classmethod(lambda cls, fast: _StubConfig(batch_size=8)),
    )
    embedding_rebuild._TELEMETRY_READY = True

    runner = CliRunner()
    result = runner.invoke(
        rebuild_embeddings_cmd,
        ["--checkpoint-file", str(checkpoint), "--resume"],
    )
    assert result.exit_code == 1
    assert "contains invalid JSON" in result.output
