"""Regression tests for running raw SQL migrations against SQLite."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from theo.infrastructure.api.app.db.run_sql_migrations import (
    _SQLITE_PERSPECTIVE_MIGRATION,
    _split_sql_statements,
    run_sql_migrations,
)
from theo.infrastructure.api.app.db.seeds import seed_reference_data


class _Base(DeclarativeBase):
    """Declarative base for lightweight test-specific models."""


class AppSetting(_Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class HarmonySeed(_Base):
    __tablename__ = "harmony_seeds"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    osis_a: Mapped[str] = mapped_column(String, nullable=False)
    osis_b: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    perspective: Mapped[str | None] = mapped_column(String, nullable=True)
    start_verse_id_a: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_verse_id_a: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_verse_id_b: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_verse_id_b: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class CommentaryExcerptSeed(_Base):
    __tablename__ = "commentary_excerpt_seeds"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    osis: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    perspective: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    start_verse_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_verse_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class GeoPlace(_Base):
    __tablename__ = "geo_places"

    slug: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    aliases: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    sources: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


@pytest.fixture(autouse=True)
def _patch_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure migrations and seeds use lightweight test models."""

    from theo.infrastructure.api.app.db import run_sql_migrations as migrations_module
    from theo.infrastructure.api.app.db import seeds as seeds_module

    monkeypatch.setattr(migrations_module, "AppSetting", AppSetting)
    monkeypatch.setattr(seeds_module, "HarmonySeed", HarmonySeed)
    monkeypatch.setattr(seeds_module, "CommentaryExcerptSeed", CommentaryExcerptSeed)
    monkeypatch.setattr(seeds_module, "GeoPlace", GeoPlace)


def test_run_sql_migrations_applies_sqlite_columns(tmp_path) -> None:
    """Ensure migrations add the perspective column before seeding."""

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)

    # Provide the metadata tables required by the migration tracker.
    AppSetting.__table__.create(bind=engine)

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
                created_at TIMESTAMP NOT NULL
            )
            """
        )

    sqlite_migrations = tmp_path / "migrations"
    sqlite_migrations.mkdir()

    migration_name = "0001_add_perspective.sql"
    sqlite_migrations.joinpath(migration_name).write_text(
        """
        ALTER TABLE contradiction_seeds
            ADD COLUMN perspective TEXT;
        """,
        encoding="utf-8",
    )

    applied = run_sql_migrations(engine, migrations_path=sqlite_migrations)

    assert migration_name in applied

    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("contradiction_seeds")}
    assert "perspective" in columns


def test_run_sql_migrations_skips_existing_sqlite_column(tmp_path) -> None:
    """Ensure the SQLite perspective migration is a no-op once applied."""

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)

    AppSetting.__table__.create(bind=engine)

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
                perspective TEXT,
                created_at TIMESTAMP NOT NULL
            )
            """
        )

    sqlite_migrations = tmp_path / "migrations"
    sqlite_migrations.mkdir()

    migration_path = (
        Path(__file__).resolve().parents[2]
        / "theo"
        / "services"
        / "api"
        / "app"
        / "db"
        / "migrations"
        / _SQLITE_PERSPECTIVE_MIGRATION
    )
    sqlite_migrations.joinpath(_SQLITE_PERSPECTIVE_MIGRATION).write_text(
        migration_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    applied = run_sql_migrations(engine, migrations_path=sqlite_migrations)

    assert _SQLITE_PERSPECTIVE_MIGRATION in applied

    with Session(engine) as session:
        setting = session.get(
            AppSetting,
            f"db:migration:{_SQLITE_PERSPECTIVE_MIGRATION}",
        )
        assert setting is not None


def test_run_sql_migrations_reapplies_when_ledger_stale(tmp_path) -> None:
    """Ensure the perspective migration reruns when the ledger entry is stale."""

    engine = create_engine(f"sqlite:///{tmp_path / 'stale.db'}", future=True)

    AppSetting.__table__.create(bind=engine)

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
                created_at TIMESTAMP NOT NULL
            )
            """
        )

    # Simulate a stale ledger entry indicating the migration has already run.
    with Session(engine) as session:
        session.add(
            AppSetting(
                key=f"db:migration:{_SQLITE_PERSPECTIVE_MIGRATION}",
                value={"applied_at": "2025-01-30T00:00:00+00:00"},
            )
        )
        session.commit()

    sqlite_migrations = tmp_path / "migrations"
    sqlite_migrations.mkdir()

    migration_path = (
        Path(__file__).resolve().parents[2]
        / "theo"
        / "services"
        / "api"
        / "app"
        / "db"
        / "migrations"
        / _SQLITE_PERSPECTIVE_MIGRATION
    )
    sqlite_migrations.joinpath(_SQLITE_PERSPECTIVE_MIGRATION).write_text(
        migration_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    applied = run_sql_migrations(engine, migrations_path=sqlite_migrations)

    assert _SQLITE_PERSPECTIVE_MIGRATION in applied

    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("contradiction_seeds")}
    assert "perspective" in columns

    with Session(engine) as session:
        setting = session.get(
            AppSetting,
            f"db:migration:{_SQLITE_PERSPECTIVE_MIGRATION}",
        )
        assert setting is not None


def test_run_sql_migrations_executes_python_migrations(tmp_path) -> None:
    """Python migration modules should be executed and recorded."""

    engine = create_engine(f"sqlite:///{tmp_path / 'python.db'}", future=True)
    AppSetting.__table__.create(bind=engine)

    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()

    migration_path = migrations_dir / "0002_create_marker.py"
    migration_path.write_text(
        """
from sqlalchemy import text


def apply(session):
    session.execute(text("CREATE TABLE py_marker (id INTEGER PRIMARY KEY)") )
        """.strip(),
        encoding="utf-8",
    )

    applied = run_sql_migrations(engine, migrations_path=migrations_dir)

    assert "0002_create_marker.py" in applied

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "py_marker" in tables


def test_seed_reference_data_tolerates_missing_perspective_column(
    tmp_path, monkeypatch
) -> None:
    """Seeding should not crash when the SQLite table is missing perspective."""

    engine = create_engine(f"sqlite:///{tmp_path / 'drift.db'}", future=True)

    HarmonySeed.__table__.create(bind=engine)
    CommentaryExcerptSeed.__table__.create(bind=engine)
    GeoPlace.__table__.create(bind=engine)

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
                created_at TIMESTAMP NOT NULL
            )
            """
        )

    from theo.infrastructure.api.app.db import seeds as seeds_module

    monkeypatch.setattr(seeds_module, "seed_openbible_geo", lambda session: None)

    with Session(engine) as session:
        seed_reference_data(session)


def test_split_sql_statements_handles_comments_and_dollar_quotes() -> None:
    """Ensure SQL splitting respects comments and PostgreSQL dollar quotes."""

    sql = """
    INSERT INTO demo VALUES ('value; still string');
    /* block comment with ; inside */
    DO $$BEGIN
        PERFORM 1;
        -- inline comment with ; inside;
        PERFORM 2;
    END$$;
    """

    statements = _split_sql_statements(sql)

    assert len(statements) == 2
    assert "INSERT INTO demo VALUES" in statements[0]
    assert statements[1].lstrip().startswith("/* block comment")
    assert "inline comment" in statements[1]
    assert statements[1].strip().endswith("END$$")


def test_run_sql_migrations_creates_performance_indexes(tmp_path) -> None:
    """Index enforcement should create the expected SQLite indexes."""

    engine = create_engine(f"sqlite:///{tmp_path / 'indexes.db'}", future=True)
    AppSetting.__table__.create(bind=engine)

    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE documents (
                id TEXT PRIMARY KEY,
                updated_at TIMESTAMP NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE passages (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                embedding BLOB,
                text TEXT
            )
            """
        )

    empty_migrations = tmp_path / "migrations"
    empty_migrations.mkdir()

    applied = run_sql_migrations(engine, migrations_path=empty_migrations)
    assert applied == []

    with engine.connect() as connection:
        passage_indexes = {
            row[1]
            for row in connection.execute(text("PRAGMA index_list('passages')"))
        }
        document_indexes = {
            row[1]
            for row in connection.execute(text("PRAGMA index_list('documents')"))
        }

    assert "idx_passages_embedding_null" in passage_indexes
    assert "idx_passages_document_id" in passage_indexes
    assert "idx_documents_updated_at" in document_indexes
