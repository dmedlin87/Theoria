from __future__ import annotations

import json
import shutil
import sqlite3
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Any
from uuid import uuid5

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.application.facades import database as database_module
from theo.application.facades.database import configure_engine, get_engine
from theo.adapters.persistence.models import (
    ContradictionSeed,
    Document,
    Passage,
    PassageVerse,
)
from theo.services.api.app.db.seeds import CONTRADICTION_NAMESPACE
from theo.services.api.app.ingest.osis import expand_osis_reference
from theo.services.api.app.main import app
from theo.services.api.app.routes.ai.workflows.exports import _CSL_TYPE_MAP, _build_csl_entry


CONTRADICTIONS_PATH = PROJECT_ROOT / "data" / "seeds" / "contradictions.json"
CONTRADICTION_SEEDS: list[dict[str, Any]] = json.loads(
    CONTRADICTIONS_PATH.read_text(encoding="utf-8")
)
assert CONTRADICTION_SEEDS, "Expected bundled contradiction seeds to be present"

MIGRATION_FILENAME = "20250129_add_perspective_to_contradiction_seeds.sql"
MIGRATION_LEDGER_KEY = f"db:migration:{MIGRATION_FILENAME}"


def _legacy_identifier(entry: dict[str, Any]) -> str:
    osis_a = entry["osis_a"].lower()
    osis_b = entry["osis_b"].lower()
    source = (entry.get("source") or "community").lower()
    perspective = (entry.get("perspective") or "skeptical").strip().lower()
    return str(
        uuid5(
            CONTRADICTION_NAMESPACE,
            "|".join([osis_a, osis_b, source, perspective]),
        )
    )


def _ledger_value() -> str:
    return json.dumps(
        {
            "applied_at": "2024-01-01T00:00:00+00:00",
            "filename": MIGRATION_FILENAME,
        }
    )


@pytest.fixture(scope="module")
def module_api_engine(
    tmp_path_factory: pytest.TempPathFactory, _api_engine_template: Path
) -> Generator[Engine, None, None]:
    database_path = tmp_path_factory.mktemp("ai-citation-export") / "api.sqlite"
    shutil.copy2(_api_engine_template, database_path)
    configure_engine(f"sqlite:///{database_path}")
    engine = get_engine()

    try:
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]


@pytest.fixture(scope="module")
def module_api_test_client(module_api_engine) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


def _seed_sample_passage(engine: Engine) -> None:
    with Session(engine) as session:
        if session.get(Document, "doc-1") is not None:
            return

        document = Document(
            id="doc-1",
            title="Sample Document",
            authors=["Jane Doe"],
            doi="10.1234/example",
            source_url="https://example.test",
            source_type="article",
            collection="Test",
            year=2024,
            abstract="Example abstract",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        john_ids = list(sorted(expand_osis_reference("John.1.1")))
        passage = Passage(
            id="passage-1",
            document_id="doc-1",
            text="In the beginning was the Word.",
            osis_ref="John.1.1",
            osis_verse_ids=john_ids,
            page_no=1,
            t_start=0.0,
            t_end=5.0,
        )
        session.add(document)
        session.add(passage)
        session.add_all(
            [PassageVerse(passage_id=passage.id, verse_id=verse_id) for verse_id in john_ids]
        )
        session.commit()


@pytest.fixture(scope="module")
def client(
    module_api_engine, module_api_test_client
) -> Generator[TestClient, None, None]:
    _seed_sample_passage(module_api_engine)
    yield module_api_test_client


@pytest.mark.schema
def test_api_startup_recovers_missing_perspective_column(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "legacy.sqlite"
    database_url = f"sqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    first_entry = CONTRADICTION_SEEDS[0]
    osis_a = first_entry["osis_a"]
    osis_b = first_entry["osis_b"]
    source = first_entry.get("source") or "community"
    perspective = (first_entry.get("perspective") or "skeptical").strip().lower()
    legacy_identifier = _legacy_identifier(first_entry)

    ledger_value = _ledger_value()

    _bootstrap_legacy_contradiction_database(
        database_url, ledger_value, first_entry, legacy_identifier
    )

    previous_engine = database_module._engine
    previous_session_factory = database_module._SessionLocal

    try:
        configure_engine(database_url)

        with TestClient(app) as test_client:
            with Session(get_engine()) as session:
                columns = session.execute(
                    text("PRAGMA table_info('contradiction_seeds')")
                ).all()
                assert any(column[1] == "perspective" for column in columns)
                perspective_value = session.execute(
                    text(
                        "SELECT perspective FROM contradiction_seeds WHERE id = :identifier"
                    ),
                    {"identifier": legacy_identifier},
                ).scalar_one()
                assert perspective_value == perspective

            with Session(get_engine()) as session:
                document = Document(
                    id="doc-legacy",
                    title="Legacy Document",
                    authors=["Legacy Author"],
                    doi="10.1234/legacy",
                    source_url="https://legacy.test",
                    source_type="article",
                    collection="Legacy",
                    year=2023,
                    abstract="Legacy abstract",
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                osis_reference = "John.1.1"
                john_ids = list(sorted(expand_osis_reference(osis_reference)))
                passage = Passage(
                    id="passage-legacy",
                    document_id=document.id,
                    text="Legacy passage",
                    osis_ref=osis_reference,
                    osis_verse_ids=john_ids,
                    page_no=1,
                    t_start=0.0,
                    t_end=5.0,
                )
                session.add(document)
                session.add(passage)
                session.add_all(
                    [
                        PassageVerse(passage_id=passage.id, verse_id=verse_id)
                        for verse_id in john_ids
                    ]
                )
                session.commit()

            response = test_client.post(
                "/ai/citations/export",
                json={
                    "citations": [
                        {
                            "index": 1,
                            "osis": "John.1.1",
                            "anchor": "John 1:1",
                            "passage_id": "passage-legacy",
                            "document_id": "doc-legacy",
                            "document_title": "Legacy Document",
                            "snippet": "Legacy passage",
                        }
                    ]
                },
            )

            assert response.status_code == 200
    finally:
        if database_module._engine is not None:
            database_module._engine.dispose()
        database_module._engine = previous_engine
        database_module._SessionLocal = previous_session_factory


@pytest.mark.schema
def test_api_startup_handles_operational_error_from_missing_columns(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "legacy-error.sqlite"
    database_url = f"sqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    first_entry = CONTRADICTION_SEEDS[0]
    osis_a = first_entry["osis_a"]
    osis_b = first_entry["osis_b"]
    source = first_entry.get("source") or "community"
    perspective = (first_entry.get("perspective") or "skeptical").strip().lower()
    legacy_identifier = _legacy_identifier(first_entry)

    ledger_value = _ledger_value()

    _bootstrap_legacy_contradiction_database(
        database_url, ledger_value, first_entry, legacy_identifier
    )

    previous_engine = database_module._engine
    previous_session_factory = database_module._SessionLocal

    failure_state = {"raised": False}
    original_get = Session.get

    def _raising_get(self, entity, ident, **kwargs):  # type: ignore[override]
        if not failure_state["raised"] and entity is ContradictionSeed:
            failure_state["raised"] = True
            raise OperationalError(
                "SELECT * FROM contradiction_seeds",  # nosec B608 - test-only literal
                {},
                sqlite3.OperationalError(
                    "no such column: contradiction_seeds.created_at"
                ),
            )
        return original_get(self, entity, ident, **kwargs)

    monkeypatch.setattr(Session, "get", _raising_get)

    try:
        configure_engine(database_url)
        with TestClient(app) as test_client:
            response = test_client.get("/health")
            assert response.status_code == 200

        inspector = inspect(get_engine())
        columns = inspector.get_columns("contradiction_seeds")
        column_names = {column["name"] for column in columns}
        assert "perspective" in column_names
        assert "created_at" in column_names
        assert failure_state["raised"], "Expected patched Session.get to raise"

        with Session(get_engine()) as session:
            session.execute(
                text(
                    "SELECT perspective FROM contradiction_seeds WHERE id = :identifier"
                ),
                {"identifier": legacy_identifier},
            ).fetchall()
    finally:
        if database_module._engine is not None:
            database_module._engine.dispose()
        database_module._engine = previous_engine
        database_module._SessionLocal = previous_session_factory


def test_export_citations_returns_csl_payload(client: TestClient) -> None:
    response = client.post(
        "/ai/citations/export",
        json={
            "citations": [
                {
                    "index": 1,
                    "osis": "John.1.1",
                    "anchor": "John 1:1",
                    "passage_id": "passage-1",
                    "document_id": "doc-1",
                    "document_title": "Sample Document",
                    "snippet": "In the beginning was the Word.",
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["manifest"]["type"] == "documents"
    assert payload["records"][0]["document_id"] == "doc-1"
    passage_meta = payload["records"][0]["passages"][0]["meta"]
    assert passage_meta["anchor"] == "John 1:1"
    assert payload["csl"][0]["title"] == "Sample Document"
    assert payload["csl"][0]["DOI"] == "10.1234/example"
    assert payload["manager_payload"]["format"] == "csl-json"
    assert payload["manager_payload"]["zotero"]["items"][0]["id"] == "doc-1"


def test_export_citations_allows_missing_source_url(client: TestClient) -> None:
    response = client.post(
        "/ai/citations/export",
        json={
            "citations": [
                {
                    "index": 1,
                    "osis": "John.1.1",
                    "anchor": "John 1:1",
                    "passage_id": "passage-1",
                    "document_id": "doc-1",
                    "document_title": "Sample Document",
                    "snippet": "In the beginning was the Word.",
                    "source_url": None,
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()

    manifest = payload["manifest"]
    record = payload["records"][0]
    csl_entry = payload["csl"][0]
    manager_items = payload["manager_payload"]["zotero"]["items"][0]

    assert manifest.get("source_url") is None
    assert record.get("source_url") is None
    assert "URL" not in csl_entry
    assert "URL" not in manager_items

    assert record["document_id"] == "doc-1"
    assert record["doi"] == "10.1234/example"
    assert record["authors"] == ["Jane Doe"]
    assert csl_entry["title"] == "Sample Document"
    assert csl_entry["DOI"] == "10.1234/example"


def test_export_citations_rejects_empty_payload(client: TestClient) -> None:
    response = client.post("/ai/citations/export", json={"citations": []})
    assert response.status_code == 400


def test_export_citations_reports_missing_document(client: TestClient) -> None:
    response = client.post(
        "/ai/citations/export",
        json={
            "citations": [
                {
                    "index": 1,
                    "osis": "John.1.1",
                    "anchor": "John 1:1",
                    "passage_id": "missing",
                    "document_id": "doc-unknown",
                    "document_title": "Missing",
                    "snippet": "Unknown",
                }
            ]
        },
    )
    assert response.status_code == 404



def test_export_citations_requires_document_id(client: TestClient) -> None:
    citation = {
        "index": 1,
        "osis": "John.1.1",
        "anchor": "John 1:1",
        "passage_id": "passage-1",
        "document_title": "Sample Document",
        "snippet": "In the beginning was the Word.",
    }

    response = client.post(
        "/ai/citations/export",
        json={"citations": [{**citation, "document_id": ""}]},
    )

    assert response.status_code == 400
    payload = response.json()
    assert "document_id" in payload.get("detail", "")
    assert "manifest" not in payload
    assert "records" not in payload

@pytest.mark.parametrize(
    "source_type, expected",
    [
        ("sermon", _CSL_TYPE_MAP["sermon"]),
        ("video", _CSL_TYPE_MAP["video"]),
        ("web", _CSL_TYPE_MAP["web"]),
        ("unknown", "article-journal"),
    ],
)
def test_build_csl_entry_uses_expected_type(source_type: str, expected: str) -> None:
    record = {
        "document_id": "doc-type-test",
        "title": "CSL Type Sample",
        "source_type": source_type,
    }

    entry = _build_csl_entry(record, citations=[])

    assert entry["type"] == expected


@pytest.mark.schema
def test_sqlite_migration_backfills_contradiction_perspective(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'pre-migration.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    from theo.application.facades import database as database_module
    from theo.application.facades import settings as settings_module
    from theo.services.api.app.db import run_sql_migrations as migrations_module
    from theo.services.api.app.db import seeds as seeds_module

    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    migration_source = (
        PROJECT_ROOT
        / "theo"
        / "services"
        / "api"
        / "app"
        / "db"
        / "migrations"
        / "20250129_add_perspective_to_contradiction_seeds.sql"
    )
    migrations_dir.joinpath(migration_source.name).write_text(
        migration_source.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(migrations_module, "MIGRATIONS_PATH", migrations_dir)

    settings_module.get_settings.cache_clear()
    engine = database_module.configure_engine()

    def _fail_on_missing_perspective(
        session: Session, dataset_label: str, exc: OperationalError
    ) -> bool:
        raise AssertionError(
            "OperationalError encountered while seeding contradiction data"
        ) from exc

    monkeypatch.setattr(
        seeds_module,
        "_handle_missing_perspective_error",
        _fail_on_missing_perspective,
    )

    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE contradiction_seeds (
                id TEXT PRIMARY KEY,
                osis_a TEXT NOT NULL,
                osis_b TEXT NOT NULL,
                summary TEXT,
                source TEXT,
                tags JSON,
                weight FLOAT NOT NULL DEFAULT 1.0,
                start_verse_id_a INTEGER,
                end_verse_id_a INTEGER,
                start_verse_id INTEGER,
                end_verse_id INTEGER,
                start_verse_id_b INTEGER,
                end_verse_id_b INTEGER,
                created_at TIMESTAMP NOT NULL
            )
            """
        )

    try:
        with TestClient(app) as seeded_client:
            response = seeded_client.get(
                "/research/contradictions",
                params=[("osis", "Luke.2.1-7")],
            )

            assert response.status_code == 200
            payload = response.json()
            assert payload["items"], "expected contradiction seeds to load"

        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("contradiction_seeds")}
        assert "perspective" in columns
    finally:
        engine.dispose()
        settings_module.get_settings.cache_clear()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]
def _bootstrap_legacy_contradiction_database(
    database_url: str, ledger_value: str, entry: dict, legacy_identifier: str
) -> None:
    bootstrap_engine = create_engine(database_url, future=True)
    try:
        with bootstrap_engine.begin() as connection:
            connection.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.exec_driver_sql(
                """
                INSERT INTO app_settings (key, value, created_at, updated_at)
                VALUES (:key, :value, :created, :updated)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                {
                    "key": MIGRATION_LEDGER_KEY,
                    "value": ledger_value,
                    "created": "2024-01-01T00:00:00+00:00",
                    "updated": "2024-01-01T00:00:00+00:00",
                },
            )
            connection.exec_driver_sql(
                """
                CREATE TABLE contradiction_seeds (
                    id TEXT PRIMARY KEY,
                    osis_a TEXT NOT NULL,
                    osis_b TEXT NOT NULL,
                    summary TEXT,
                    source TEXT,
                    tags TEXT,
                    weight REAL DEFAULT 1.0,
                    start_verse_id_a INTEGER,
                    end_verse_id_a INTEGER,
                    start_verse_id INTEGER,
                    end_verse_id INTEGER,
                    start_verse_id_b INTEGER,
                    end_verse_id_b INTEGER,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.exec_driver_sql(
                """
                INSERT INTO contradiction_seeds (
                    id, osis_a, osis_b, summary, source, tags, weight,
                    start_verse_id_a, end_verse_id_a,
                    start_verse_id, end_verse_id,
                    start_verse_id_b, end_verse_id_b,
                    created_at
                ) VALUES (
                    :id, :osis_a, :osis_b, :summary, :source, :tags, :weight,
                    NULL, NULL,
                    NULL, NULL,
                    NULL, NULL,
                    :created_at
                )
                """,
                {
                    "id": legacy_identifier,
                    "osis_a": entry["osis_a"],
                    "osis_b": entry["osis_b"],
                    "summary": entry.get("summary"),
                    "source": entry.get("source") or "community",
                    "tags": json.dumps(entry.get("tags")),
                    "weight": float(entry.get("weight", 1.0)),
                    "created_at": "2024-01-01T00:00:00+00:00",
                },
            )
    finally:
        bootstrap_engine.dispose()

