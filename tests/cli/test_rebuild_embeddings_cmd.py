from __future__ import annotations

import importlib
import json
import logging
import sys
import types

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, List

import importlib.machinery as importlib_machinery

import pytest
from click.testing import CliRunner

try:  # pragma: no cover - optional dependency in lightweight test runs
    from sqlalchemy.exc import SQLAlchemyError
except ModuleNotFoundError:  # pragma: no cover - exercised when dependency missing
    class SQLAlchemyError(Exception):
        """Fallback SQLAlchemyError when the real dependency is unavailable."""


@pytest.fixture
def cli_module(
    stub_sqlalchemy: types.ModuleType, stub_pythonbible: types.ModuleType
) -> Iterator[types.ModuleType]:
    """Import :mod:`theo.cli` with stubbed heavy dependencies."""

from theo.application.embeddings import (
    EmbeddingRebuildError,
    EmbeddingRebuildOptions,
    EmbeddingRebuildProgress,
    EmbeddingRebuildResult,
    EmbeddingRebuildService,
    EmbeddingRebuildStart,
    EmbeddingRebuildState,
)
try:  # pragma: no cover - optional dependency in lightweight test runs
    from sqlalchemy.exc import SQLAlchemyError
except ModuleNotFoundError:  # pragma: no cover - exercised when dependency missing

if "fastapi" not in sys.modules:
    fastapi_stub = types.ModuleType("fastapi")
    fastapi_stub.status = types.SimpleNamespace()
    sys.modules["fastapi"] = fastapi_stub

def _install_sqlalchemy_stub() -> None:
    if "sqlalchemy" in sys.modules:
        return
    try:  # Prefer the real package when available.
        import importlib

        importlib.import_module("sqlalchemy")
        return
    except ModuleNotFoundError:
        pass

    from importlib.machinery import ModuleSpec

    sqlalchemy_stub = types.ModuleType("sqlalchemy")
    sqlalchemy_stub.__path__ = []  # type: ignore[attr-defined]
    sqlalchemy_spec = ModuleSpec("sqlalchemy", loader=None, is_package=True)
    sqlalchemy_spec.submodule_search_locations = []  # type: ignore[assignment]
    sqlalchemy_stub.__spec__ = sqlalchemy_spec  # type: ignore[attr-defined]

    class _FuncProxy:
        def __getattr__(self, name: str) -> Any:  # pragma: no cover - defensive
            raise NotImplementedError(
                f"sqlalchemy.func placeholder accessed for '{name}'"
            )

    def _raise(*_args: object, **_kwargs: object) -> None:  # pragma: no cover
        raise NotImplementedError("sqlalchemy placeholder accessed")

    sqlalchemy_stub.__theoria_sqlalchemy_stub__ = True
    sqlalchemy_stub.__path__ = []
    sqlalchemy_stub.__spec__ = importlib_machinery.ModuleSpec(
        "sqlalchemy", loader=None, is_package=True
    )
    sqlalchemy_stub.func = _FuncProxy()
    sqlalchemy_stub.select = _raise
    sqlalchemy_stub.create_engine = _raise
    sqlalchemy_stub.text = lambda statement: statement

    exc_module = types.ModuleType("sqlalchemy.exc")

    class SQLAlchemyError(Exception):
        """Fallback SQLAlchemyError when the real dependency is unavailable."""


@pytest.fixture
def cli_module(
    stub_sqlalchemy: types.ModuleType, stub_pythonbible: types.ModuleType
) -> Iterator[types.ModuleType]:
    """Import :mod:`theo.cli` with stubbed heavy dependencies."""

    module_name = "theo.cli"
    original = sys.modules.pop(module_name, None)
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if original is not None:
            sys.modules[module_name] = original
        pytest.skip(f"theo.cli unavailable: {exc}")
    try:
        yield module
    finally:
        sys.modules.pop(module_name, None)
        if original is not None:
            sys.modules[module_name] = original


@pytest.fixture
def rebuild_embeddings_cmd(cli_module: types.ModuleType):
    return cli_module.rebuild_embeddings_cmd


@pytest.fixture
def cli(cli_module: types.ModuleType):
    return cli_module.cli


@dataclass
class FakePassageRow:
    id: str
    text: str
    embedding: list[float] | None
    document_updated_at: datetime | None = None


class FakeCriterion:
    def __init__(self, op: str, getter, value: Any) -> None:
        self.op = op
        self.getter = getter
        self.value = value



@pytest.fixture
def rebuild_embeddings_cmd(cli_module: types.ModuleType):
    return cli_module.rebuild_embeddings_cmd




@pytest.fixture
def cli_module(
    stub_sqlalchemy: types.ModuleType, stub_pythonbible: types.ModuleType
) -> Iterator[types.ModuleType]:
    """Import :mod:`theo.cli` with stubbed heavy dependencies."""

    module_name = "theo.cli"
    original = sys.modules.pop(module_name, None)
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if original is not None:
            sys.modules[module_name] = original
        pytest.skip(f"theo.cli unavailable: {exc}")
    try:
        yield module
    finally:
        sys.modules.pop(module_name, None)
        if original is not None:
            sys.modules[module_name] = original


@pytest.fixture
def rebuild_embeddings_cmd(cli_module: types.ModuleType):
    return cli_module.rebuild_embeddings_cmd


@pytest.fixture
def cli(cli_module: types.ModuleType):
    return cli_module.cli
    sql_module = types.ModuleType("sqlalchemy.sql")
    sql_module.__path__ = []  # type: ignore[attr-defined]
    sql_module.__package__ = "sqlalchemy"
    sql_spec = ModuleSpec("sqlalchemy.sql", loader=None, is_package=True)
    sql_spec.submodule_search_locations = []  # type: ignore[assignment]
    sql_module.__spec__ = sql_spec  # type: ignore[attr-defined]
    elements_module = types.ModuleType("sqlalchemy.sql.elements")
    elements_module.__package__ = "sqlalchemy.sql"
    elements_spec = ModuleSpec("sqlalchemy.sql.elements", loader=None, is_package=False)
    elements_spec.submodule_search_locations = []  # type: ignore[assignment]
    elements_module.__spec__ = elements_spec  # type: ignore[attr-defined]

    class ClauseElement:  # pragma: no cover - placeholder type
        pass

    elements_module.ClauseElement = ClauseElement
    sql_module.elements = elements_module  # type: ignore[attr-defined]

    sqlalchemy_stub.exc = exc_module
    sqlalchemy_stub.orm = orm_module
    sqlalchemy_stub.engine = engine_module
    sql_module = types.ModuleType("sqlalchemy.sql")
    sql_module.__path__ = []
    sql_module.__spec__ = importlib_machinery.ModuleSpec(
        "sqlalchemy.sql", loader=None, is_package=True
    )
    elements_module = types.ModuleType("sqlalchemy.sql.elements")
    elements_module.__spec__ = importlib_machinery.ModuleSpec(
        "sqlalchemy.sql.elements", loader=None, is_package=True
    )

    class ClauseElement:  # pragma: no cover - placeholder
        pass

    elements_module.ClauseElement = ClauseElement
    sql_module.elements = elements_module
    sqlalchemy_stub.sql = sql_module

    sys.modules["sqlalchemy"] = sqlalchemy_stub
    sys.modules["sqlalchemy.exc"] = exc_module
    sys.modules["sqlalchemy.orm"] = orm_module
    sys.modules["sqlalchemy.engine"] = engine_module
    sys.modules["sqlalchemy.sql"] = sql_module
    sys.modules["sqlalchemy.sql.elements"] = elements_module


def _install_pythonbible_stub() -> None:
    if "pythonbible" in sys.modules:
        return
    try:
        import importlib

        importlib.import_module("pythonbible")
        return
    except ModuleNotFoundError:
        pass

    module = types.ModuleType("pythonbible")

    class _BookEntry:
        def __init__(self, name: str) -> None:
            self.name = name

        def __repr__(self) -> str:  # pragma: no cover - debug helper
            return f"Book.{self.name}"

        def __hash__(self) -> int:
            return hash(self.name)

        def __eq__(self, other: object) -> bool:
            return isinstance(other, _BookEntry) and other.name == self.name

    class _BookMeta(type):
        def __iter__(cls) -> Iterable["_BookEntry"]:  # pragma: no cover
            return iter(cls._members)

    class Book(metaclass=_BookMeta):
        _members: list[_BookEntry] = []

    def _register(name: str) -> _BookEntry:
        entry = _BookEntry(name)
        setattr(Book, name, entry)
        Book._members.append(entry)
        return entry

    for book_name in [
        "GENESIS",
        "EXODUS",
        "LEVITICUS",
        "NUMBERS",
        "DEUTERONOMY",
        "JOSHUA",
        "JUDGES",
        "RUTH",
        "SAMUEL_1",
        "SAMUEL_2",
        "KINGS_1",
        "KINGS_2",
        "CHRONICLES_1",
        "CHRONICLES_2",
        "EZRA",
        "NEHEMIAH",
        "ESTHER",
        "JOB",
        "PSALMS",
        "PROVERBS",
        "ECCLESIASTES",
        "SONG_OF_SONGS",
        "ISAIAH",
        "JEREMIAH",
        "LAMENTATIONS",
        "EZEKIEL",
        "DANIEL",
        "HOSEA",
        "JOEL",
        "AMOS",
        "OBADIAH",
        "JONAH",
        "MICAH",
        "NAHUM",
        "HABAKKUK",
        "ZEPHANIAH",
        "HAGGAI",
        "ZECHARIAH",
        "MALACHI",
        "MATTHEW",
        "MARK",
        "LUKE",
        "JOHN",
        "ACTS",
        "ROMANS",
        "CORINTHIANS_1",
        "CORINTHIANS_2",
        "GALATIANS",
        "EPHESIANS",
        "PHILIPPIANS",
        "COLOSSIANS",
        "THESSALONIANS_1",
        "THESSALONIANS_2",
        "TIMOTHY_1",
        "TIMOTHY_2",
        "TITUS",
        "PHILEMON",
        "HEBREWS",
        "JAMES",
        "PETER_1",
        "PETER_2",
        "JOHN_1",
        "JOHN_2",
        "JOHN_3",
        "JUDE",
        "REVELATION",
        "TOBIT",
        "WISDOM_OF_SOLOMON",
        "ECCLESIASTICUS",
        "ESDRAS_1",
        "MACCABEES_1",
        "MACCABEES_2",
    ]:
        _register(book_name)

    @dataclass(frozen=True)
    class NormalizedReference:
        book: _BookEntry
        start_chapter: int
        start_verse: int
        end_chapter: int
        end_verse: int

    def is_valid_verse_id(verse_id: int) -> bool:  # pragma: no cover - stub
        return isinstance(verse_id, int) and verse_id >= 0

    module.Book = Book
    module.NormalizedReference = NormalizedReference
    module.is_valid_verse_id = is_valid_verse_id

    sys.modules["pythonbible"] = module


def _install_fastapi_stub() -> None:
    if "fastapi" in sys.modules:
        return

    fastapi_module = types.ModuleType("fastapi")
    status_module = types.ModuleType("fastapi.status")
    # Provide the attributes referenced during import
    status_module.HTTP_422_UNPROCESSABLE_ENTITY = 422
    status_module.HTTP_422_UNPROCESSABLE_CONTENT = 422
    fastapi_module.status = status_module  # type: ignore[attr-defined]

    sys.modules["fastapi"] = fastapi_module
    sys.modules["fastapi.status"] = status_module


def _install_opentelemetry_stub() -> None:
    if "opentelemetry" in sys.modules:
        return

    opentelemetry_module = types.ModuleType("opentelemetry")
    trace_module = types.ModuleType("opentelemetry.trace")

    class _Span:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def set_attribute(self, *_args, **_kwargs) -> None:
            return None

    class _Tracer:
        def start_as_current_span(self, *_args, **_kwargs):
            return _Span()

    def get_tracer(*_args, **_kwargs) -> _Tracer:
        return _Tracer()

    def get_current_span() -> _Span:
        return _Span()

    trace_module.get_tracer = get_tracer  # type: ignore[assignment]
    trace_module.get_current_span = get_current_span  # type: ignore[assignment]
    opentelemetry_module.trace = trace_module  # type: ignore[attr-defined]

    sys.modules["opentelemetry"] = opentelemetry_module
    sys.modules["opentelemetry.trace"] = trace_module


_install_sqlalchemy_stub()
_install_pythonbible_stub()
_install_fastapi_stub()
_install_opentelemetry_stub()

from sqlalchemy.exc import SQLAlchemyError

from theo.checkpoints import CURRENT_EMBEDDING_CHECKPOINT_VERSION
from theo.cli import cli, rebuild_embeddings_cmd


class StubEmbeddingRebuildService(EmbeddingRebuildService):
    def __init__(self) -> None:
        self.calls: list[EmbeddingRebuildOptions] = []
        self.progress_events: list[EmbeddingRebuildProgress] = []
        self.start_events: list[EmbeddingRebuildStart] = []
        self.result = EmbeddingRebuildResult(
            processed=1,
            total=1,
            duration=0.5,
            missing_ids=[],
            metadata={},
        )

    # type: ignore[override]
    def rebuild_embeddings(
        self,
        options: EmbeddingRebuildOptions,
        *,
        on_start=None,
        on_progress=None,
    ) -> EmbeddingRebuildResult:
        self.calls.append(options)
        if on_start is not None:
            start = EmbeddingRebuildStart(total=1, missing_ids=[], skip_count=0)
            self.start_events.append(start)
            on_start(start)
        if on_progress is not None:
            state = EmbeddingRebuildState(
                processed=1,
                total=1,
                last_id="p1",
                metadata=options.metadata,
            )
            progress = EmbeddingRebuildProgress(
                batch_index=1,
                batch_size=1,
                batch_duration=0.1,
                rate_per_passage=0.1,
                state=state,
            )
            self.progress_events.append(progress)
            on_progress(progress)
        return self.result


class FailingEmbeddingRebuildService(StubEmbeddingRebuildService):
    def rebuild_embeddings(self, *args: Any, **kwargs: Any) -> EmbeddingRebuildResult:
        raise EmbeddingRebuildError("boom")


class FakeRegistry:
    def __init__(self, service: EmbeddingRebuildService) -> None:
        self.service = service

    def resolve(self, name: str) -> EmbeddingRebuildService:
        if name != "embedding_rebuild_service":  # pragma: no cover - defensive
            raise LookupError(name)
        return self.service


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def _patch_registry(monkeypatch: pytest.MonkeyPatch, service: EmbeddingRebuildService) -> None:
    def _resolve_application() -> tuple[object, FakeRegistry]:
        return object(), FakeRegistry(service)

    monkeypatch.setattr("theo.cli.resolve_application", _resolve_application)
def test_rebuild_embeddings_fast_ids_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    runner: CliRunner,
    rebuild_embeddings_cmd,
) -> None:
    env = FakeCLIEnvironment(monkeypatch)
    env.add_passage(
        id="p1",
        text="First passage",
        embedding=None,
        document_updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    env.add_passage(
        id="p2",
        text="Second passage",
        embedding=None,
        document_updated_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )
    env.embedding_service.queue_response([[0.1, 0.2]])

    ids_path = tmp_path / "ids.txt"
    ids_path.write_text("p1\nmissing\n", encoding="utf-8")
    checkpoint_path = tmp_path / "checkpoint.json"

    result = runner.invoke(
        rebuild_embeddings_cmd,
        ["--fast", "--ids-file", str(ids_path), "--checkpoint-file", str(checkpoint_path)],
    )

    assert result.exit_code == 0, result.output
    assert env.embedding_service.embed_calls == [(["First passage"], 64)]
    assert "1 passage ID(s) were not found and will be skipped." in result.output
    assert "Rebuilding embeddings for 1 passage(s) using batch size 64." in result.output
    assert "Batch 1: updated 1/1 passages in" in result.output
    assert f"Checkpoint written to {checkpoint_path}" in result.output
    assert "Completed embedding rebuild for 1 passage(s)" in result.output

    checkpoint_data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert (
        checkpoint_data["version"] == CURRENT_EMBEDDING_CHECKPOINT_VERSION
    )
    assert checkpoint_data["processed"] == 1
    assert checkpoint_data["total"] == 1
    assert checkpoint_data["last_id"] == "p1"
    assert "created_at" in checkpoint_data
    assert "updated_at" in checkpoint_data
    metadata = checkpoint_data["metadata"]
    assert metadata == {
        "fast": True,
        "changed_since": None,
        "ids_file": str(ids_path),
        "ids_count": 2,
        "resume": False,
    }

    assert env.passages[0].embedding == [0.1, 0.2]


def test_rebuild_embeddings_resume_from_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    runner: CliRunner,
    rebuild_embeddings_cmd,
) -> None:
    env = FakeCLIEnvironment(monkeypatch)
    env.add_passage(id="p1", text="First", embedding=None)
    env.add_passage(id="p2", text="Second", embedding=None)
    env.embedding_service.queue_response([[0.9, 0.1]])

    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint_path.write_text(
        json.dumps({"processed": 1, "total": 2, "last_id": "p1"}),
        encoding="utf-8",
    )


def test_cli_rebuild_embeddings_invokes_service(monkeypatch: pytest.MonkeyPatch, runner: CliRunner) -> None:
    service = StubEmbeddingRebuildService()
    _patch_registry(monkeypatch, service)

    result = runner.invoke(rebuild_embeddings_cmd, ["--fast"])

    assert result.exit_code == 0, result.output
    assert "Resuming from checkpoint" in result.output
    assert "Batch 1: updated 2/2 passages in" in result.output
    assert f"Checkpoint written to {checkpoint_path}" in result.output
    assert "Completed embedding rebuild for 2 passage(s)" in result.output

    assert env.embedding_service.embed_calls == [(["Second"], 128)]

    updated_data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert (
        updated_data["version"] == CURRENT_EMBEDDING_CHECKPOINT_VERSION
    )
    assert updated_data["processed"] == 2
    assert updated_data["total"] == 2
    assert updated_data["last_id"] == "p2"
    assert "created_at" in updated_data
    assert "updated_at" in updated_data
    assert updated_data["metadata"] == {
        "fast": False,
        "changed_since": None,
        "ids_file": None,
        "ids_count": None,
        "resume": True,
    }


def test_rebuild_embeddings_resume_with_invalid_checkpoint_logs_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    runner: CliRunner,
    caplog: pytest.LogCaptureFixture,
) -> None:
    FakeCLIEnvironment(monkeypatch)
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint_path.write_text("{invalid", encoding="utf-8")

    caplog.set_level(logging.ERROR, logger="theo.cli")

    result = runner.invoke(
        rebuild_embeddings_cmd,
        ["--checkpoint-file", str(checkpoint_path), "--resume"],
    )

    assert result.exit_code == 1
    assert "contains invalid JSON" in result.output

    error_records = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert error_records, "Expected an error log when checkpoint decoding fails"
    record = error_records[-1]
    assert record.event == "cli.rebuild_embeddings.checkpoint_decode_error"
    assert record.checkpoint_file == str(checkpoint_path)


def test_rebuild_embeddings_errors_on_mismatched_vectors(
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    rebuild_embeddings_cmd,
) -> None:
    env = FakeCLIEnvironment(monkeypatch)
    env.add_passage(id="p1", text="Only", embedding=None)
    env.embedding_service.queue_response([])

    result = runner.invoke(rebuild_embeddings_cmd, ["--fast"])

    assert result.exit_code == 1
    assert "Embedding backend returned mismatched batch size" in result.output


def test_rebuild_embeddings_clears_cache_when_requested(
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    rebuild_embeddings_cmd,
) -> None:
    env = FakeCLIEnvironment(monkeypatch)
    env.add_passage(id="p1", text="Only", embedding=None)
    env.embedding_service.queue_response([[0.5, 0.5]])

    result = runner.invoke(rebuild_embeddings_cmd, ["--no-cache", "--fast"])

    assert result.exit_code == 0, result.output
    assert "Rebuilding embeddings for 1 passage(s)" in result.output
    assert "Batch 1: updated 1/1 passages" in result.output
    assert "Completed embedding rebuild for 1 passage(s)" in result.output
    assert service.calls


def test_cli_handles_checkpoint_resume(monkeypatch: pytest.MonkeyPatch, runner: CliRunner, tmp_path: Path) -> None:
    service = StubEmbeddingRebuildService()
    _patch_registry(monkeypatch, service)
def test_cli_help_lists_rebuild_command(runner: CliRunner, cli) -> None:
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "rebuild_embeddings" in result.output

    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(json.dumps({"processed": 2}), encoding="utf-8")

    result = runner.invoke(
        rebuild_embeddings_cmd,
        ["--checkpoint-file", str(checkpoint), "--resume"],
    )
def test_rebuild_embeddings_invalid_changed_since_format(
    runner: CliRunner, rebuild_embeddings_cmd
) -> None:
    result = runner.invoke(rebuild_embeddings_cmd, ["--changed-since", "not-a-date"])
    assert result.exit_code == 2
    assert "Invalid value for '--changed-since'" in result.output

    assert result.exit_code == 0, result.output
    assert "Resuming from checkpoint" in result.output
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert payload["processed"] == 1
    assert payload["total"] == 1
    assert payload["last_id"] == "p1"
    assert "Checkpoint written" in result.output

def test_rebuild_embeddings_requires_existing_ids_file(
    runner: CliRunner, tmp_path: Path, rebuild_embeddings_cmd
) -> None:
    missing_path = tmp_path / "missing.txt"
    result = runner.invoke(rebuild_embeddings_cmd, ["--ids-file", str(missing_path)])
    assert result.exit_code == 2
    assert "Invalid value for '--ids-file'" in result.output

def test_cli_handles_empty_ids_file(monkeypatch: pytest.MonkeyPatch, runner: CliRunner, tmp_path: Path) -> None:
    service = StubEmbeddingRebuildService()
    _patch_registry(monkeypatch, service)

    ids_file = tmp_path / "ids.txt"
    ids_file.write_text("\n\n", encoding="utf-8")

def test_rebuild_embeddings_handles_empty_ids_file(
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    tmp_path: Path,
    rebuild_embeddings_cmd,
) -> None:
    env = FakeCLIEnvironment(monkeypatch)
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text("\n\n", encoding="utf-8")

    result = runner.invoke(rebuild_embeddings_cmd, ["--fast", "--ids-file", str(ids_file)])

    assert result.exit_code == 0
    assert "No passage IDs were found" in result.output
    assert env.embedding_service.embed_calls == []


def test_rebuild_embeddings_fast_skips_existing_embeddings(
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    rebuild_embeddings_cmd,
) -> None:
    env = FakeCLIEnvironment(monkeypatch)
    env.add_passage(id="p1", text="New", embedding=None)
    env.add_passage(id="p2", text="Old", embedding=[0.0, 0.1])

    result = runner.invoke(rebuild_embeddings_cmd, ["--fast"])

    assert result.exit_code == 0, result.output
    assert env.embedding_service.embed_calls == [(["New"], 64)]
    assert env.passages[0].embedding is not None
    assert env.passages[1].embedding == [0.0, 0.1]
    assert "Rebuilding embeddings for 1 passage(s) using batch size 64." in result.output


def test_rebuild_embeddings_uses_standard_batch_size_when_not_fast(
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    rebuild_embeddings_cmd,
) -> None:
    env = FakeCLIEnvironment(monkeypatch)
    env.add_passage(id="p1", text="One", embedding=None)

    result = runner.invoke(rebuild_embeddings_cmd, [])

    assert result.exit_code == 0, result.output
    assert env.embedding_service.embed_calls == [(["One"], 128)]
    assert "Rebuilding embeddings for 1 passage(s) using batch size 128." in result.output


def test_rebuild_embeddings_changed_since_filters_passages(
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    tmp_path: Path,
    rebuild_embeddings_cmd,
) -> None:
    env = FakeCLIEnvironment(monkeypatch)
    env.add_passage(
        id="p1",
        text="Early",
        embedding=None,
        document_updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    env.add_passage(
        id="p2",
        text="Recent",
        embedding=None,
        document_updated_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
    )
    env.add_passage(
        id="p3",
        text="Latest",
        embedding=None,
        document_updated_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
    )

    checkpoint = tmp_path / "checkpoint.json"
    result = runner.invoke(
        rebuild_embeddings_cmd,
        ["--ids-file", str(ids_file)],
    )

    assert result.exit_code == 0, result.output
    assert "No passage IDs were found" in result.output


def test_cli_handles_service_error(monkeypatch: pytest.MonkeyPatch, runner: CliRunner) -> None:
    service = FailingEmbeddingRebuildService()
    _patch_registry(monkeypatch, service)
    assert len(env.embedding_service.embed_calls) == 1
    assert env.embedding_service.embed_calls[0][0] == ["Recent", "Latest"]
    checkpoint_data = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert (
        checkpoint_data["version"] == CURRENT_EMBEDDING_CHECKPOINT_VERSION
    )
    assert checkpoint_data["metadata"]["changed_since"] == "2024-02-01T00:00:00+00:00"
    assert env.passages[0].embedding is None
    assert env.passages[1].embedding is not None
    assert env.passages[2].embedding is not None


def test_rebuild_embeddings_processes_multiple_batches(
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    rebuild_embeddings_cmd,
) -> None:
    env = FakeCLIEnvironment(monkeypatch)
    for idx in range(65):
        env.add_passage(id=f"p{idx:03d}", text=f"Passage {idx}", embedding=None)

    result = runner.invoke(rebuild_embeddings_cmd, ["--fast"])

    assert result.exit_code == 0, result.output
    assert len(env.embedding_service.embed_calls) == 2
    assert len(env.embedding_service.embed_calls[0][0]) == 64
    assert len(env.embedding_service.embed_calls[1][0]) == 1
    assert "Batch 2" in result.output


def test_rebuild_embeddings_handles_application_resolution_failure(
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    rebuild_embeddings_cmd,
) -> None:
    def _fail() -> tuple[object, object]:
        raise RuntimeError("boom")

    monkeypatch.setattr("theo.cli.resolve_application", _fail)

    result = runner.invoke(rebuild_embeddings_cmd, ["--fast"])

    assert result.exit_code == 1
    assert "boom" in result.output

    assert "Failed to resolve application" in result.output


def test_rebuild_embeddings_handles_session_initialisation_error(
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    rebuild_embeddings_cmd,
) -> None:
    class _Registry:
        def __init__(self, engine: object) -> None:
            self.engine = engine

        def resolve(self, name: str) -> object:
            assert name == "engine"
            return self.engine

    engine = object()
    monkeypatch.setattr("theo.cli.resolve_application", lambda: (object(), _Registry(engine)))

    def _failing_session(_engine: object) -> None:
        raise SQLAlchemyError("cannot connect")

    monkeypatch.setattr("theo.cli.Session", _failing_session)
    monkeypatch.setattr(
        "theo.cli.get_embedding_service",
        lambda: types.SimpleNamespace(embed=lambda texts, batch_size: [[0.0] * batch_size for _ in texts]),
    )
    monkeypatch.setattr(
        "theo.cli.Passage",
        types.SimpleNamespace(embedding=types.SimpleNamespace(is_=lambda _value: None)),
    )

    result = runner.invoke(rebuild_embeddings_cmd, ["--fast"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SQLAlchemyError)

def test_cli_help_lists_rebuild_command(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "rebuild_embeddings" in result.output

def test_rebuild_embeddings_reports_embedding_backend_failure(
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    rebuild_embeddings_cmd,
) -> None:
    env = FakeCLIEnvironment(monkeypatch)
    env.add_passage(id="p1", text="Only", embedding=None)

def test_cli_handles_application_resolution_failure(monkeypatch: pytest.MonkeyPatch, runner: CliRunner) -> None:
    def _fail() -> tuple[object, object]:
        raise RuntimeError("boom")

    monkeypatch.setattr("theo.cli.resolve_application", _fail)

    result = runner.invoke(rebuild_embeddings_cmd, ["--fast"])

    assert result.exit_code == 1
    assert "Failed to resolve application" in result.output
    


def test_rebuild_embeddings_resume_with_missing_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    tmp_path: Path,
    rebuild_embeddings_cmd,
) -> None:
    env = FakeCLIEnvironment(monkeypatch)
    env.add_passage(id="p1", text="Only", embedding=None)

    checkpoint = tmp_path / "checkpoint.json"

    result = runner.invoke(
        rebuild_embeddings_cmd,
        ["--checkpoint-file", str(checkpoint), "--resume"],
    )

    assert result.exit_code == 0, result.output
    assert "Resuming from checkpoint" not in result.output
    assert env.embedding_service.embed_calls == [(["Only"], 128)]


def test_rebuild_embeddings_integration_with_sqlite(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner, tmp_path: Path
) -> None:
    sqlalchemy = pytest.importorskip("sqlalchemy")
    if getattr(sqlalchemy, "__theoria_sqlalchemy_stub__", False):
        pytest.skip("sqlalchemy stub active")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as SQLASession

    from theo.cli import rebuild_embeddings_cmd
    from theo.adapters.persistence.models import Base, Document, Passage

    db_path = tmp_path / "theo.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[Document.__table__, Passage.__table__])

    with SQLASession(engine) as session:
        doc1 = Document(id="d1", title="Doc 1")
        doc1.updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        doc2 = Document(id="d2", title="Doc 2")
        doc2.updated_at = datetime(2024, 2, 1, tzinfo=timezone.utc)
        session.add_all([doc1, doc2])
        session.flush()
        passage1 = Passage(id="p1", document_id=doc1.id, text="Doc 1 text", embedding=None)
        passage2 = Passage(id="p2", document_id=doc2.id, text="Doc 2 text", embedding=None)
        session.add_all([passage1, passage2])
        session.commit()

    class _IntegrationRegistry:
        def __init__(self, engine: object) -> None:
            self.engine = engine

        def resolve(self, name: str) -> object:
            assert name == "engine"
            return self.engine

    class _SimpleEmbeddingService:
        def __init__(self) -> None:
            self.calls: list[tuple[list[str], int]] = []

        def embed(self, texts: list[str], *, batch_size: int) -> list[list[float]]:
            self.calls.append((list(texts), batch_size))
            return [[0.1, 0.2] for _ in texts]

    embedding_service = _SimpleEmbeddingService()
    cache_calls: list[bool] = []

    monkeypatch.setattr(
        "theo.cli.resolve_application",
        lambda: (object(), _IntegrationRegistry(engine)),
    )
    monkeypatch.setattr("theo.cli.get_embedding_service", lambda: embedding_service)
    monkeypatch.setattr("theo.cli.clear_embedding_cache", lambda: cache_calls.append(True))

    ids_file = tmp_path / "ids.txt"
    ids_file.write_text("p2\n", encoding="utf-8")
    checkpoint = tmp_path / "checkpoint.json"

    result = runner.invoke(
        rebuild_embeddings_cmd,
        [
            "--no-cache",
            "--changed-since",
            "2024-02-01",
            "--ids-file",
            str(ids_file),
            "--checkpoint-file",
            str(checkpoint),
        ],
    )

    assert result.exit_code == 0, result.output
    assert cache_calls == [True]
    assert embedding_service.calls == [(["Doc 2 text"], 128)]

    with SQLASession(engine) as session:
        refreshed = session.get(Passage, "p2")
        assert refreshed is not None
        assert refreshed.embedding == [0.1, 0.2]
        skipped = session.get(Passage, "p1")
        assert skipped is not None
        assert skipped.embedding is None

    checkpoint_data = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert (
        checkpoint_data["version"] == CURRENT_EMBEDDING_CHECKPOINT_VERSION
    )
    assert checkpoint_data["processed"] == 1
    assert checkpoint_data["metadata"]["ids_count"] == 1
