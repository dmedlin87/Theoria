from __future__ import annotations

import json
import sys
import types

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List

import pytest
from click.testing import CliRunner


def _install_sqlalchemy_stub() -> None:
    if "sqlalchemy" in sys.modules:
        return
    try:  # Prefer the real package when available.
        import importlib

        importlib.import_module("sqlalchemy")
        return
    except ModuleNotFoundError:
        pass

    sqlalchemy_stub = types.ModuleType("sqlalchemy")

    class _FuncProxy:
        def __getattr__(self, name: str) -> Any:  # pragma: no cover - defensive
            raise NotImplementedError(
                f"sqlalchemy.func placeholder accessed for '{name}'"
            )

    def _raise(*_args: object, **_kwargs: object) -> None:  # pragma: no cover
        raise NotImplementedError("sqlalchemy placeholder accessed")

    sqlalchemy_stub.__theoria_sqlalchemy_stub__ = True
    sqlalchemy_stub.func = _FuncProxy()
    sqlalchemy_stub.select = _raise
    sqlalchemy_stub.create_engine = _raise
    sqlalchemy_stub.text = lambda statement: statement

    exc_module = types.ModuleType("sqlalchemy.exc")

    class SQLAlchemyError(Exception):
        """Stub SQLAlchemyError used for import-time compatibility."""

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

    sqlalchemy_stub.exc = exc_module
    sqlalchemy_stub.orm = orm_module
    sqlalchemy_stub.engine = engine_module

    sys.modules["sqlalchemy"] = sqlalchemy_stub
    sys.modules["sqlalchemy.exc"] = exc_module
    sys.modules["sqlalchemy.orm"] = orm_module
    sys.modules["sqlalchemy.engine"] = engine_module


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


_install_sqlalchemy_stub()
_install_pythonbible_stub()

from sqlalchemy.exc import SQLAlchemyError

from theo.cli import cli, rebuild_embeddings_cmd


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


class FakeColumn:
    def __init__(self, name: str, getter) -> None:
        self.name = name
        self.getter = getter

    def in_(self, values: Iterable[str]) -> "FakeCriterion":
        return FakeCriterion("in", self.getter, tuple(values))

    def is_(self, value: Any) -> "FakeCriterion":
        return FakeCriterion("is", self.getter, value)

    def __ge__(self, other: Any) -> "FakeCriterion":
        return FakeCriterion("ge", self.getter, other)


class FakePassageModel:
    id = FakeColumn("id", lambda row: row.id)
    embedding = FakeColumn("embedding", lambda row: row.embedding)


class FakeDocumentModel:
    updated_at = FakeColumn(
        "document_updated_at", lambda row: getattr(row, "document_updated_at", None)
    )


class FakeFunc:
    def count(self, column: FakeColumn) -> tuple[str, FakeColumn]:
        return ("count", column)


class FakeSelect:
    def __init__(self, mode: str, column: FakeColumn | None = None) -> None:
        self.mode = mode
        self.column = column
        self.filters: list[FakeCriterion] = []
        self.order_getter = None
        self.execution_kwargs: dict[str, Any] = {}

    def select_from(self, _entity: object) -> "FakeSelect":
        return self

    def where(self, criterion: FakeCriterion) -> "FakeSelect":
        self.filters.append(criterion)
        return self

    def join(self, _entity: object) -> "FakeSelect":
        return self

    def order_by(self, column: FakeColumn) -> "FakeSelect":
        self.order_getter = column.getter
        return self

    def execution_options(self, **kwargs: Any) -> "FakeSelect":
        self.execution_kwargs.update(kwargs)
        return self


def fake_select(target: object) -> FakeSelect:
    if isinstance(target, tuple) and target and target[0] == "count":
        return FakeSelect("count")
    if isinstance(target, FakeColumn):
        return FakeSelect("ids", column=target)
    if target is FakePassageModel:
        return FakeSelect("passages")
    raise AssertionError(f"Unexpected select target: {target!r}")


class FakeResult:
    def __init__(self, values: List[Any]) -> None:
        self._values = values

    def scalar_one(self) -> Any:
        if not self._values:
            raise AssertionError("No scalar available")
        return self._values[0]

    def scalars(self) -> Iterable[Any]:
        return iter(self._values)


class FakeRegistry:
    def __init__(self, engine: object) -> None:
        self.engine = engine
        self.resolved: list[str] = []

    def resolve(self, name: str) -> object:
        self.resolved.append(name)
        if name != "engine":
            raise KeyError(name)
        return self.engine


class FakeEmbeddingService:
    def __init__(self) -> None:
        self.embed_calls: list[tuple[list[str], int]] = []
        self._responses: list[list[list[float]]] = []

    def queue_response(self, vectors: list[list[float]]) -> None:
        self._responses.append(vectors)

    def embed(self, texts: list[str], *, batch_size: int) -> list[list[float]]:
        self.embed_calls.append((list(texts), batch_size))
        if self._responses:
            return self._responses.pop(0)
        return [[float(idx)] for idx, _ in enumerate(texts)]


class FakeSession:
    def __init__(self, env: "FakeCLIEnvironment") -> None:
        self.env = env
        self.bulk_updates: list[list[dict[str, Any]]] = []
        self.commits = 0
        self.rollback_called = False

    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None

    def execute(self, stmt: FakeSelect) -> FakeResult:
        filtered = self._apply_filters(stmt.filters)
        if stmt.mode == "count":
            return FakeResult([len(filtered)])
        if stmt.mode == "ids":
            assert stmt.column is not None
            values = [stmt.column.getter(row) for row in filtered]
            return FakeResult(values)
        if stmt.mode == "passages":
            items = list(filtered)
            if stmt.order_getter is not None:
                items.sort(key=stmt.order_getter)
            return FakeResult(items)
        raise AssertionError(f"Unknown select mode: {stmt.mode}")

    def bulk_update_mappings(self, _model: object, payload: list[dict[str, Any]]) -> None:
        self.bulk_updates.append(payload)
        for entry in payload:
            for row in self.env.passages:
                if row.id == entry["id"]:
                    row.embedding = entry.get("embedding")
                    break

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollback_called = True

    def _apply_filters(self, filters: list[FakeCriterion]) -> list[FakePassageRow]:
        items = self.env.passages
        for criterion in filters:
            items = [row for row in items if self._match(row, criterion)]
        return items

    @staticmethod
    def _match(row: FakePassageRow, criterion: FakeCriterion) -> bool:
        value = criterion.getter(row)
        if criterion.op == "is":
            if criterion.value is None:
                return value is None
            return value is criterion.value
        if criterion.op == "in":
            return value in criterion.value
        if criterion.op == "ge":
            if value is None:
                return False
            return value >= criterion.value
        raise AssertionError(f"Unsupported criterion: {criterion.op}")


class FakeCLIEnvironment:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.passages: list[FakePassageRow] = []
        self.embedding_service = FakeEmbeddingService()
        self.clear_cache_called = False
        self.registry = FakeRegistry(object())

        monkeypatch.setattr("theo.cli.resolve_application", self._resolve_application)
        monkeypatch.setattr("theo.cli.Session", lambda _engine: FakeSession(self))
        monkeypatch.setattr("theo.cli.get_embedding_service", lambda: self.embedding_service)
        monkeypatch.setattr("theo.cli.clear_embedding_cache", self._clear_embedding_cache)
        monkeypatch.setattr("theo.cli.select", fake_select)
        monkeypatch.setattr("theo.cli.func", FakeFunc())
        monkeypatch.setattr("theo.cli.Passage", FakePassageModel)
        monkeypatch.setattr("theo.cli.Document", FakeDocumentModel)

    def _resolve_application(self) -> tuple[object, FakeRegistry]:
        return object(), self.registry

    def _clear_embedding_cache(self) -> None:
        self.clear_cache_called = True

    def add_passage(
        self,
        *,
        id: str,
        text: str,
        embedding: list[float] | None = None,
        document_updated_at: datetime | None = None,
    ) -> FakePassageRow:
        row = FakePassageRow(
            id=id,
            text=text,
            embedding=embedding,
            document_updated_at=document_updated_at,
        )
        self.passages.append(row)
        return row


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_rebuild_embeddings_fast_ids_checkpoint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, runner: CliRunner
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
    assert checkpoint_data["processed"] == 1
    assert checkpoint_data["total"] == 1
    assert checkpoint_data["last_id"] == "p1"
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
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, runner: CliRunner
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

    result = runner.invoke(
        rebuild_embeddings_cmd,
        ["--checkpoint-file", str(checkpoint_path), "--resume"],
    )

    assert result.exit_code == 0, result.output
    assert "Resuming from checkpoint" in result.output
    assert "Batch 1: updated 2/2 passages in" in result.output
    assert f"Checkpoint written to {checkpoint_path}" in result.output
    assert "Completed embedding rebuild for 2 passage(s)" in result.output

    assert env.embedding_service.embed_calls == [(["Second"], 128)]

    updated_data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert updated_data["processed"] == 2
    assert updated_data["total"] == 2
    assert updated_data["last_id"] == "p2"
    assert updated_data["metadata"] == {
        "fast": False,
        "changed_since": None,
        "ids_file": None,
        "ids_count": None,
        "resume": True,
    }


def test_rebuild_embeddings_errors_on_mismatched_vectors(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    env = FakeCLIEnvironment(monkeypatch)
    env.add_passage(id="p1", text="Only", embedding=None)
    env.embedding_service.queue_response([])

    result = runner.invoke(rebuild_embeddings_cmd, ["--fast"])

    assert result.exit_code == 1
    assert "Embedding backend returned mismatched batch size" in result.output


def test_rebuild_embeddings_clears_cache_when_requested(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    env = FakeCLIEnvironment(monkeypatch)
    env.add_passage(id="p1", text="Only", embedding=None)
    env.embedding_service.queue_response([[0.5, 0.5]])

    result = runner.invoke(rebuild_embeddings_cmd, ["--no-cache", "--fast"])

    assert result.exit_code == 0, result.output
    assert env.clear_cache_called is True
    assert "Completed embedding rebuild for 1 passage(s)" in result.output


def test_cli_help_lists_rebuild_command(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "rebuild_embeddings" in result.output


def test_rebuild_embeddings_invalid_changed_since_format(runner: CliRunner) -> None:
    result = runner.invoke(rebuild_embeddings_cmd, ["--changed-since", "not-a-date"])
    assert result.exit_code == 2
    assert "Invalid value for '--changed-since'" in result.output


def test_rebuild_embeddings_requires_existing_ids_file(
    runner: CliRunner, tmp_path: Path
) -> None:
    missing_path = tmp_path / "missing.txt"
    result = runner.invoke(rebuild_embeddings_cmd, ["--ids-file", str(missing_path)])
    assert result.exit_code == 2
    assert "Invalid value for '--ids-file'" in result.output


def test_rebuild_embeddings_handles_empty_ids_file(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner, tmp_path: Path
) -> None:
    env = FakeCLIEnvironment(monkeypatch)
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text("\n\n", encoding="utf-8")

    result = runner.invoke(rebuild_embeddings_cmd, ["--fast", "--ids-file", str(ids_file)])

    assert result.exit_code == 0
    assert "No passage IDs were found" in result.output
    assert env.embedding_service.embed_calls == []


def test_rebuild_embeddings_fast_skips_existing_embeddings(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
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
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    env = FakeCLIEnvironment(monkeypatch)
    env.add_passage(id="p1", text="One", embedding=None)

    result = runner.invoke(rebuild_embeddings_cmd, [])

    assert result.exit_code == 0, result.output
    assert env.embedding_service.embed_calls == [(["One"], 128)]
    assert "Rebuilding embeddings for 1 passage(s) using batch size 128." in result.output


def test_rebuild_embeddings_changed_since_filters_passages(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner, tmp_path: Path
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
        [
            "--changed-since",
            "2024-02-01T00:00:00",
            "--checkpoint-file",
            str(checkpoint),
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(env.embedding_service.embed_calls) == 1
    assert env.embedding_service.embed_calls[0][0] == ["Recent", "Latest"]
    checkpoint_data = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert checkpoint_data["metadata"]["changed_since"] == "2024-02-01T00:00:00+00:00"
    assert env.passages[0].embedding is None
    assert env.passages[1].embedding is not None
    assert env.passages[2].embedding is not None


def test_rebuild_embeddings_processes_multiple_batches(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
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
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    def _fail() -> tuple[object, object]:
        raise RuntimeError("boom")

    monkeypatch.setattr("theo.cli.resolve_application", _fail)

    result = runner.invoke(rebuild_embeddings_cmd, ["--fast"])

    assert result.exit_code == 1
    assert "Failed to resolve application" in result.output


def test_rebuild_embeddings_handles_session_initialisation_error(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
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

    result = runner.invoke(rebuild_embeddings_cmd, ["--fast"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SQLAlchemyError)


def test_rebuild_embeddings_reports_embedding_backend_failure(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    env = FakeCLIEnvironment(monkeypatch)
    env.add_passage(id="p1", text="Only", embedding=None)

    def _raise(_texts: list[str], *, batch_size: int) -> list[list[float]]:
        raise RuntimeError("backend offline")

    monkeypatch.setattr(env.embedding_service, "embed", _raise)

    result = runner.invoke(rebuild_embeddings_cmd, ["--fast"])

    assert result.exit_code == 1
    assert "Embedding generation failed" in result.output


def test_rebuild_embeddings_resume_with_missing_checkpoint(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner, tmp_path: Path
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
    assert checkpoint_data["processed"] == 1
    assert checkpoint_data["metadata"]["ids_count"] == 1
