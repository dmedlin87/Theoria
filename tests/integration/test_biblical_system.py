"""Comprehensive integration coverage for biblical workflows and infrastructure."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette import status as starlette_status

if not hasattr(starlette_status, "HTTP_422_UNPROCESSABLE_CONTENT"):
    starlette_status.HTTP_422_UNPROCESSABLE_CONTENT = (  # type: ignore[attr-defined]
        starlette_status.HTTP_422_UNPROCESSABLE_ENTITY
    )

import sys
import types


def _install_sklearn_stub() -> None:
    if "sklearn" in sys.modules:
        return

    sklearn_module = types.ModuleType("sklearn")
    ensemble_module = types.ModuleType("sklearn.ensemble")
    cluster_module = types.ModuleType("sklearn.cluster")

    class _StubIsolationForest:
        def __init__(self, *_, **__):
            pass

        def fit(self, *_args, **_kwargs):
            return self

        def decision_function(self, embeddings):
            return [0.0 for _ in range(len(embeddings) or 0)]

        def predict(self, embeddings):
            return [1 for _ in range(len(embeddings) or 0)]

    ensemble_module.IsolationForest = _StubIsolationForest  # type: ignore[attr-defined]
    sklearn_module.ensemble = ensemble_module  # type: ignore[attr-defined]

    class _StubDBSCAN:
        def __init__(self, *_, **__):
            pass

        def fit_predict(self, embeddings):
            return [0 for _ in range(len(embeddings) or 0)]

    cluster_module.DBSCAN = _StubDBSCAN  # type: ignore[attr-defined]
    sklearn_module.cluster = cluster_module  # type: ignore[attr-defined]

    sys.modules["sklearn"] = sklearn_module
    sys.modules["sklearn.ensemble"] = ensemble_module
    sys.modules["sklearn.cluster"] = cluster_module


_install_sklearn_stub()


def _install_celery_stub() -> None:
    if "celery" in sys.modules:
        return

    celery_module = types.ModuleType("celery")

    class _StubCelery:
        def __init__(self, *_, **__):
            self.conf = types.SimpleNamespace(
                task_always_eager=True,
                task_ignore_result=True,
                task_store_eager_result=False,
            )

        def task(self, *args, **kwargs):  # pragma: no cover - used for decorators
            def decorator(func):
                return func

            return decorator

    celery_module.Celery = _StubCelery  # type: ignore[attr-defined]

    celery_app_module = types.ModuleType("celery.app")
    celery_task_module = types.ModuleType("celery.app.task")

    class _StubTask:
        abstract = False

    celery_task_module.Task = _StubTask  # type: ignore[attr-defined]
    celery_app_module.task = celery_task_module  # type: ignore[attr-defined]

    celery_exceptions_module = types.ModuleType("celery.exceptions")

    class _StubRetry(Exception):
        pass

    celery_exceptions_module.Retry = _StubRetry  # type: ignore[attr-defined]

    celery_schedules_module = types.ModuleType("celery.schedules")

    def _crontab(*_args, **_kwargs):  # pragma: no cover - simple stub
        return {"type": "crontab"}

    celery_schedules_module.crontab = _crontab  # type: ignore[attr-defined]

    celery_utils_module = types.ModuleType("celery.utils")
    celery_utils_log_module = types.ModuleType("celery.utils.log")

    def _get_task_logger(name: str):  # pragma: no cover - logging stub
        class _StubLogger:
            def info(self, *_args, **_kwargs):
                return None

            def error(self, *_args, **_kwargs):
                return None

        return _StubLogger()

    celery_utils_log_module.get_task_logger = _get_task_logger  # type: ignore[attr-defined]
    celery_utils_module.log = celery_utils_log_module  # type: ignore[attr-defined]

    sys.modules["celery"] = celery_module
    sys.modules["celery.app"] = celery_app_module
    sys.modules["celery.app.task"] = celery_task_module
    sys.modules["celery.exceptions"] = celery_exceptions_module
    sys.modules["celery.schedules"] = celery_schedules_module
    sys.modules["celery.utils"] = celery_utils_module
    sys.modules["celery.utils.log"] = celery_utils_log_module

    celery_result_module = types.ModuleType("celery.result")

    class _StubAsyncResult:
        def __init__(self, task_id: str, *_, **__):
            self.id = task_id
            self.state = "SUCCESS"

        def ready(self) -> bool:
            return True

        def get(self, *_, **__):
            return None

    celery_result_module.AsyncResult = _StubAsyncResult  # type: ignore[attr-defined]
    sys.modules["celery.result"] = celery_result_module


_install_celery_stub()

from theo.adapters.biblical_ai_processor import BiblicalAIProcessor
from theo.adapters.persistence import Base, dispose_sqlite_engine
from theo.application.facades import database as database_module
from theo.application.facades.database import configure_engine, get_engine, get_session
from theo.application.facades.settings import Settings, get_settings
from theo.cli import rebuild_embeddings_cmd
from theo.domain import Document, DocumentId, DocumentMetadata
from theo.domain.biblical_texts import (
    BibleVersion,
    BiblicalBook,
    Language,
    Reference,
    TheologicalTermTracker,
)
from theo.platform.application import resolve_application
from theo.services.api.app.db import query_optimizations
from theo.services.api.app.db.run_sql_migrations import run_sql_migrations
from theo.services.api.app.main import app
from theo.services.api.app.models.search import HybridSearchFilters, HybridSearchRequest
from theo.services.api.app.persistence_models import Document as DocumentRecord
from theo.services.api.app.persistence_models import Passage
from theo.services.api.app.retriever import documents as documents_retriever
from theo.services.api.app.retriever import hybrid as hybrid_module
from theo.services.api.app.routes import documents as documents_route


@dataclass
class _StubMessage:
    content: str


@dataclass
class _StubChoice:
    message: _StubMessage


@dataclass
class _StubResponse:
    choices: List[_StubChoice]


class _FakeCompletions:
    def __init__(self, payloads: list[str]) -> None:
        self._payloads = list(payloads)

    def create(self, *_, **__) -> _StubResponse:  # pragma: no cover - deterministic stub
        if not self._payloads:
            raise AssertionError("No payloads remaining for fake AI client")
        content = self._payloads.pop(0)
        return _StubResponse([_StubChoice(_StubMessage(content))])


class _FakeChat:
    def __init__(self, payloads: list[str]) -> None:
        self.completions = _FakeCompletions(payloads)


class _FakeAIClient:
    def __init__(self, payloads: list[str]) -> None:
        self.chat = _FakeChat(payloads)


class _SpanContext:
    def __init__(self, span: "_StubSpan") -> None:
        self._span = span

    def __enter__(self) -> "_StubSpan":
        return self._span

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - no special handling
        return None


class _StubSpan:
    def __init__(self, name: str) -> None:
        self.name = name
        self.attributes: dict[str, object] = {}

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


class _StubTracer:
    def __init__(self) -> None:
        self.spans: list[_StubSpan] = []

    def start_as_current_span(self, name: str) -> _SpanContext:
        span = _StubSpan(name)
        self.spans.append(span)
        return _SpanContext(span)


@pytest.fixture(autouse=True)
def _baseline_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Provide consistent configuration for integration scenarios."""

    monkeypatch.setenv("SETTINGS_SECRET_KEY", "integration-secret")
    monkeypatch.setenv("THEO_API_KEYS", '["pytest-default-key"]')
    monkeypatch.setenv("THEO_ALLOW_INSECURE_STARTUP", "1")
    monkeypatch.setenv("THEORIA_ENVIRONMENT", "test")
    monkeypatch.setenv("THEO_FORCE_EMBEDDING_FALLBACK", "1")
    get_settings.cache_clear()
    monkeypatch.setattr(query_optimizations, "record_histogram", lambda *_, **__: None)
    monkeypatch.setattr(query_optimizations, "record_counter", lambda *_, **__: None)
    try:
        yield
    finally:
        get_settings.cache_clear()
        reset_reranker = getattr(documents_route, "reset_reranker_cache", None)
        if callable(reset_reranker):
            reset_reranker()
        resolve_application.cache_clear()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]


def _configure_temporary_engine(path: Path) -> Engine:
    database_url = f"sqlite:///{path}" if path.suffix else f"sqlite:///{path / 'db.sqlite'}"
    configure_engine(database_url)
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return engine


def test_biblical_analysis_workflow_end_to_end() -> None:
    """Validate ingestion, AI analysis, and search over biblical content."""

    morphology_payload = json.dumps(
        [
            {
                "word": "בְּרֵאשִׁית",
                "lemma": "רֵאשִׁית",
                "root": "ראש",
                "pos": "noun",
                "gender": "feminine",
                "number": "singular",
                "state": "construct",
                "gloss": "beginning",
                "theological_notes": ["creation_narrative"],
            },
            {
                "word": "בָּרָא",
                "lemma": "ברא",
                "root": "ברא",
                "pos": "verb",
                "stem": "qal",
                "tense": "perfect",
                "person": 3,
                "gender": "masculine",
                "number": "singular",
                "gloss": "create",
                "theological_notes": ["divine_creation"],
            },
            {
                "word": "אֱלֹהִים",
                "lemma": "אלהים",
                "root": "אלה",
                "pos": "noun",
                "gender": "masculine",
                "number": "plural",
                "state": "absolute",
                "gloss": "God",
                "theological_notes": ["divine_name", "plural_form_singular_verb"],
            },
        ]
    )
    semantic_payload = json.dumps(
        {
            "themes": ["creation", "cosmology"],
            "theological_keywords": ["אלהים", "ברא"],
            "cross_references": ["John.1.1"],
            "textual_variants": [],
            "translation_notes": {
                "plural": "Plural noun with singular verb emphasises divine unity",
            },
        }
    )
    processor = BiblicalAIProcessor(
        _FakeAIClient(
            [
                "Bereshit bara Elohim et hashamayim ve'et haaretz",
                morphology_payload,
                semantic_payload,
            ]
        )
    )
    reference = Reference(
        book="Genesis",
        chapter=1,
        verse=1,
        book_id="gen",
        osis_id="Gen.1.1",
    )
    verse = processor.process_hebrew_verse(
        "בְּרֵאשִׁית בָּרָא אֱלֹהִים אֵת הַשָּׁמַיִם וְאֵת הָאָרֶץ",
        reference,
    )

    assert verse.language is Language.HEBREW
    assert verse.semantic_analysis is not None
    assert "creation" in verse.semantic_analysis.themes

    book = BiblicalBook(
        id="gen",
        name="Genesis",
        native_name="בראשית",
        language=Language.HEBREW,
        chapter_count=50,
        verses={"1:1": verse},
    )
    version = BibleVersion(
        name="WLC",
        abbreviation="WLC",
        language=Language.HEBREW,
        license="public-domain",
        source_url=None,
        version="1.0",
        description="Sample dataset",
        books={"gen": book},
    )

    matches = book.search_word("אלהים", lemma=True)
    assert matches == [verse]

    divine_occurrences = TheologicalTermTracker.find_elohim_singular_verbs(version)
    assert len(divine_occurrences) == 1
    assert divine_occurrences[0].reference.osis_id == "Gen.1.1"


def test_documents_api_with_real_database_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure document APIs operate against a live transactional database."""

    real_get_document = documents_retriever.get_document

    def _get_document_with_missing(session: Session, document_id: str):
        if document_id == "missing":
            raise KeyError("Document missing")
        return real_get_document(session, document_id)

    monkeypatch.setattr(
        documents_retriever, "get_document", _get_document_with_missing
    )
    monkeypatch.setattr(documents_route, "get_document", _get_document_with_missing)

    engine = _configure_temporary_engine(tmp_path / "api.db")
    resolve_application.cache_clear()
    container, registry = resolve_application()

    document = Document(
        id=DocumentId("doc-biblical"),
        metadata=DocumentMetadata(
            title="Genesis Commentary",
            source="manuscript",
            language="hebrew",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ),
        scripture_refs=("Gen.1.1",),
        tags=("creation", "theology"),
        checksum="abc123",
    )
    container.ingest_document(document)

    def _override_session() -> Iterator[Session]:
        with Session(registry.resolve("engine")) as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            headers = {"X-API-Key": "pytest-default-key"}
            response = client.get("/documents", headers=headers)
            assert response.status_code == 200
            payload = response.json()
            assert payload["items"], "Expected document results"
            first = payload["items"][0]
            assert first["id"] == str(document.id)
            assert first["title"] == document.metadata.title
            assert first["collection"] == document.metadata.source

            missing = client.get("/documents/missing", headers=headers)
            assert missing.status_code == 404
            detail = missing.json()
            assert detail["error"]["code"] == "RETRIEVAL_DOCUMENT_NOT_FOUND"
            assert "Document missing" in detail["detail"]
    finally:
        app.dependency_overrides.pop(get_session, None)
        engine.dispose()


def test_cli_rebuild_embeddings_updates_passages(tmp_path: Path) -> None:
    """Run the CLI against a temporary database and ensure embeddings are written."""

    db_path = tmp_path / "cli.db"
    engine = _configure_temporary_engine(db_path)
    resolve_application.cache_clear()
    resolve_application()

    with Session(engine) as session:
        now = datetime.now(timezone.utc)
        record = DocumentRecord(
            id="doc-cli",
            title="Sermon on Genesis",
            collection="sermons",
            created_at=now,
            updated_at=now,
            bib_json={"language": "en"},
        )
        session.add(record)
        session.flush()
        session.add_all(
            [
                Passage(
                    id="p1",
                    document_id=record.id,
                    text="In the beginning God created the heavens and the earth.",
                    raw_text="In the beginning God created the heavens and the earth.",
                    tokens=10,
                ),
                Passage(
                    id="p2",
                    document_id=record.id,
                    text="The earth was without form and void, and darkness covered the deep.",
                    raw_text="The earth was without form and void, and darkness covered the deep.",
                    tokens=16,
                ),
            ]
        )
        session.commit()

    runner = CliRunner()
    result = runner.invoke(rebuild_embeddings_cmd, [])
    assert result.exit_code == 0
    assert "Batch" in result.output
    assert "s/pass" in result.output

    with Session(engine) as session:
        embeddings = session.query(Passage.id, Passage.embedding).filter(
            Passage.id.in_(["p1", "p2"])
        )
        vectors = {row[0]: row[1] for row in embeddings}
        assert set(vectors) == {"p1", "p2"}
        dim = get_settings().embedding_dim
        assert all(isinstance(vector, list) and len(vector) == dim for vector in vectors.values())

    dispose_sqlite_engine(engine)


def test_hybrid_search_fallback_records_latency(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Execute fallback hybrid search and capture performance instrumentation."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    tracer = _StubTracer()
    monkeypatch.setattr(hybrid_module, "_TRACER", tracer)

    with Session(engine) as session:
        now = datetime.now(timezone.utc)
        document = DocumentRecord(
            id="doc-search",
            title="Creation Theology",
            collection="research",
            created_at=now,
            updated_at=now,
            bib_json={"language": "en", "tags": ["creation"]},
        )
        session.add(document)
        session.flush()
        session.add(
            Passage(
                id="passage-search",
                document_id=document.id,
                text="Let there be light, and there was light.",
                raw_text="Let there be light, and there was light.",
                tokens=12,
                osis_ref="Gen.1.3",
            )
        )
        session.commit()

        request = HybridSearchRequest(
            query="light",
            filters=HybridSearchFilters(collection="research"),
            k=5,
        )
        results = hybrid_module.hybrid_search(session, request)

    assert results
    assert results[0].document_title == "Creation Theology"

    recorded = {span.name: span for span in tracer.spans}
    assert "retriever.fallback" in recorded
    span = recorded["retriever.fallback"]
    assert "retrieval.latency_ms" in span.attributes
    assert span.attributes["retrieval.backend"] == "fallback"

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_run_sql_migrations_and_schema_validation(tmp_path: Path) -> None:
    """Apply SQL and Python migrations and ensure the schema reflects them."""

    engine = create_engine(f"sqlite:///{tmp_path / 'migrations.db'}", future=True)
    Base.metadata.create_all(engine)

    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    migrations_dir.joinpath("0001_create_demo.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS demo_records (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );
        """,
        encoding="utf-8",
    )
    migrations_dir.joinpath("0002_seed_demo.py").write_text(
        """
from sqlalchemy import text

def upgrade(*, session, engine):
    session.execute(text("INSERT INTO demo_records (id, name) VALUES (:id, :name)"), {"id": "seed", "name": "Seeded"})
    session.commit()
        """,
        encoding="utf-8",
    )

    applied = run_sql_migrations(engine, migrations_path=migrations_dir)
    assert applied == ["0001_create_demo.sql", "0002_seed_demo.py"]

    with Session(engine) as session:
        rows = session.execute(
            text("SELECT name FROM demo_records WHERE id = :id"), {"id": "seed"}
        ).all()
        assert rows == [("Seeded",)]

    reapplied = run_sql_migrations(engine, migrations_path=migrations_dir)
    assert reapplied == []

    engine.dispose()


def test_settings_reranker_validation_across_envs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Load settings from environment variables and validate reranker constraints."""

    storage_root = tmp_path / "storage"
    reranker_root = storage_root / "rerankers"
    reranker_root.mkdir(parents=True)

    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("RERANKER_ENABLED", "true")
    monkeypatch.setenv("RERANKER_MODEL_PATH", "model.joblib")
    monkeypatch.setenv("RERANKER_MODEL_SHA256", "a" * 64)

    settings = Settings()
    expected_path = (reranker_root / "model.joblib").resolve()
    assert settings.reranker_model_path == expected_path

    monkeypatch.setenv("RERANKER_MODEL_SHA256", "invalid")
    get_settings.cache_clear()
    with pytest.raises(ValueError):
        Settings()


def test_sqlite_engine_cleanup_allows_teardown(tmp_path: Path) -> None:
    """Ensure dispose_sqlite_engine releases file handles for teardown."""

    db_path = tmp_path / "teardown.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
    dispose_sqlite_engine(engine)
    engine.dispose()
    db_path.unlink()
    assert not db_path.exists()
