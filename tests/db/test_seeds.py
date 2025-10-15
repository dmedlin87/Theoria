"""Regression tests for database seed loaders."""

from __future__ import annotations

import json
import sys
import logging
import importlib
import textwrap
from pathlib import Path

import anyio
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.application.facades.database import Base
from theo.services.api.app.db import seeds
from theo.services.api.app.db.models import (
    CommentaryExcerptSeed,
    ContradictionSeed,
    GeoPlace,
    HarmonySeed,
)


def _write_seed(path: Path, payload: list[dict]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_seeders_remove_stale_records(tmp_path, monkeypatch) -> None:
    seed_dir = tmp_path / "seeds"
    seed_dir.mkdir()

    contradictions_path = seed_dir / "contradictions.json"
    geo_places_path = seed_dir / "geo_places.json"

    first_contradiction = {
        "osis_a": "Gen.1.1",
        "osis_b": "Gen.1.2",
        "source": "test",
        "summary": "first",
    }
    stale_contradiction = {
        "osis_a": "Gen.1.3",
        "osis_b": "Gen.1.4",
        "source": "test",
        "summary": "stale",
    }
    first_geo = {
        "slug": "jerusalem",
        "name": "Jerusalem",
        "lat": 31.778,
        "lng": 35.235,
    }
    stale_geo = {
        "slug": "bethlehem",
        "name": "Bethlehem",
    }

    _write_seed(contradictions_path, [first_contradiction, stale_contradiction])
    _write_seed(geo_places_path, [first_geo, stale_geo])

    monkeypatch.setattr(seeds, "SEED_ROOT", seed_dir)

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        seeds.seed_contradiction_claims(session)
        seeds.seed_geo_places(session)

    stale_contradiction_id = seeds.uuid5(
        seeds.CONTRADICTION_NAMESPACE,
        "gen.1.3|gen.1.4|test|skeptical",
    )

    with Session(engine) as session:
        assert session.get(ContradictionSeed, str(stale_contradiction_id)) is not None
        assert session.get(GeoPlace, "bethlehem") is not None

    _write_seed(contradictions_path, [first_contradiction])
    _write_seed(geo_places_path, [first_geo])

    with Session(engine) as session:
        seeds.seed_contradiction_claims(session)
        seeds.seed_geo_places(session)

    with Session(engine) as session:
        assert session.get(ContradictionSeed, str(stale_contradiction_id)) is None
        assert session.get(GeoPlace, "bethlehem") is None
        assert session.get(ContradictionSeed, str(
            seeds.uuid5(
                seeds.CONTRADICTION_NAMESPACE,
                "gen.1.1|gen.1.2|test|skeptical",
            )
        )) is not None
        assert session.get(GeoPlace, "jerusalem") is not None


def test_seed_reference_data_repairs_missing_perspective_column(
    tmp_path, monkeypatch, caplog
) -> None:
    """Reference seeders should rebuild legacy SQLite tables missing perspective."""

    seed_dir = tmp_path / "seeds"
    seed_dir.mkdir()

    _write_seed(
        seed_dir / "contradictions.json",
        [
            {
                "osis_a": "Gen.1.1",
                "osis_b": "Gen.1.2",
                "source": "test",
                "summary": "first",
                "perspective": "skeptical",
            }
        ],
    )
    _write_seed(
        seed_dir / "harmonies.json",
        [
            {
                "osis_a": "Gen.1.1",
                "osis_b": "Gen.1.2",
                "summary": "aligned",
                "source": "test",
                "perspective": "apologetic",
            }
        ],
    )
    _write_seed(
        seed_dir / "commentaries.json",
        [
            {
                "osis": "Gen.1.1",
                "excerpt": "In the beginning...",
                "source": "test",
                "perspective": "neutral",
            }
        ],
    )

    monkeypatch.setattr(seeds, "SEED_ROOT", seed_dir)
    monkeypatch.setattr(seeds, "seed_openbible_geo", lambda session: None)
    monkeypatch.setattr(seeds, "seed_geo_places", lambda session: None)

    database_path = tmp_path / "legacy.sqlite"
    engine = create_engine(f"sqlite:///{database_path}", future=True)

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
        connection.exec_driver_sql(
            """
            CREATE TABLE harmony_seeds (
                id TEXT PRIMARY KEY,
                osis_a TEXT NOT NULL,
                osis_b TEXT NOT NULL,
                summary TEXT,
                source TEXT,
                tags JSON,
                weight FLOAT NOT NULL DEFAULT 1.0
            )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE commentary_excerpt_seeds (
                id TEXT PRIMARY KEY,
                osis TEXT NOT NULL,
                title TEXT,
                excerpt TEXT NOT NULL,
                source TEXT,
                tags JSON
            )
            """
        )

    Base.metadata.create_all(engine)

    with Session(engine) as session, caplog.at_level(logging.INFO):
        seeds.seed_reference_data(session)

    log_messages = [record.getMessage() for record in caplog.records]
    assert any(
        "Rebuilt contradiction_seeds table missing 'perspective' column" in message
        for message in log_messages
    )
    assert any(
        "Rebuilt harmony_seeds table missing 'perspective' column" in message
        for message in log_messages
    )
    assert any(
        "Rebuilt commentary_excerpt_seeds table missing 'perspective' column" in message
        for message in log_messages
    )

    with engine.connect() as connection:
        for table_name in (
            "contradiction_seeds",
            "harmony_seeds",
            "commentary_excerpt_seeds",
        ):
            result = connection.exec_driver_sql(
                f"PRAGMA table_info('{table_name}')"
            ).all()
            assert any(column[1] == "perspective" for column in result)

    with Session(engine) as session:
        contradiction_perspectives = session.scalars(
            select(ContradictionSeed.perspective)
        ).all()
        harmony_perspectives = session.scalars(
            select(HarmonySeed.perspective)
        ).all()
        commentary_perspectives = session.scalars(
            select(CommentaryExcerptSeed.perspective)
        ).all()

        assert contradiction_perspectives == ["skeptical"]
        assert harmony_perspectives == ["apologetic"]
        assert commentary_perspectives == ["neutral"]


def test_api_boots_contradiction_seeding_without_migrations(
    tmp_path, monkeypatch
) -> None:
    """Boot the API without migrations and ensure contradiction seeding succeeds."""

    db_path = tmp_path / "api.sqlite"
    bootstrap_engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with bootstrap_engine.begin() as connection:
            connection.exec_driver_sql(
                """
                CREATE TABLE contradiction_seeds (
                    id TEXT PRIMARY KEY,
                    osis_a TEXT NOT NULL,
                    osis_b TEXT NOT NULL,
                    summary TEXT,
                    source TEXT,
                    tags TEXT,
                    weight FLOAT NOT NULL DEFAULT 1.0,
                    start_verse_id_a INTEGER,
                    end_verse_id_a INTEGER,
                    start_verse_id INTEGER,
                    end_verse_id INTEGER,
                    start_verse_id_b INTEGER,
                    end_verse_id_b INTEGER,
                    created_at TIMESTAMP NOT NULL
                );
                """
            )
    finally:
        bootstrap_engine.dispose()

    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("THEO_DATABASE_URL", database_url)
    monkeypatch.setenv("THEO_ALLOW_INSECURE_STARTUP", "1")
    monkeypatch.setenv("THEORIA_ENVIRONMENT", "development")
    monkeypatch.setenv("SETTINGS_SECRET_KEY", "test-secret")

    from theo.application.facades import settings as settings_module
    settings_module.get_settings.cache_clear()
    settings_module.get_settings_cipher.cache_clear()

    from theo.application.facades import database as database_module
    database_module._engine = None  # type: ignore[attr-defined]
    database_module._SessionLocal = None  # type: ignore[attr-defined]

    if "theo.services.api.app.main" in sys.modules:
        importlib.reload(sys.modules["theo.services.api.app.main"])
    else:
        importlib.import_module("theo.services.api.app.main")
    main_module = sys.modules["theo.services.api.app.main"]

    monkeypatch.setattr(main_module, "run_sql_migrations", lambda *_, **__: [])
    from theo.services.api.app.db import run_sql_migrations as migrations_module

    monkeypatch.setattr(
        migrations_module,
        "run_sql_migrations",
        lambda *_, **__: [],
    )

    seed_dir = tmp_path / "seeds"
    seed_dir.mkdir()
    minimal_payload = [
        {
            "osis_a": "Gen.1.1",
            "osis_b": "Gen.1.2",
            "source": "test",
            "summary": "first",
            "perspective": "skeptical",
        }
    ]
    (seed_dir / "contradictions.json").write_text(
        json.dumps(minimal_payload), encoding="utf-8"
    )

    from theo.services.api.app.db import seeds as seeds_module

    monkeypatch.setattr(seeds_module, "SEED_ROOT", seed_dir)
    monkeypatch.setattr(seeds_module, "seed_harmony_claims", lambda session: None)
    monkeypatch.setattr(
        seeds_module, "seed_commentary_excerpts", lambda session: None
    )
    monkeypatch.setattr(seeds_module, "seed_geo_places", lambda session: None)
    monkeypatch.setattr(seeds_module, "seed_openbible_geo", lambda session: None)

    app = main_module.create_app()

    async def _run_lifespan() -> None:
        async with app.router.lifespan_context(app):
            pass

    anyio.run(_run_lifespan)

    verification_engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with verification_engine.connect() as connection:
            columns = [
                row[1]
                for row in connection.exec_driver_sql(
                    "PRAGMA table_info('contradiction_seeds')"
                )
            ]
            assert "perspective" in columns
            count = connection.exec_driver_sql(
                "SELECT COUNT(*) FROM contradiction_seeds"
            ).scalar_one()
            assert count > 0
    finally:
        verification_engine.dispose()

    if database_module._engine is not None:  # type: ignore[attr-defined]
        database_module._engine.dispose()  # type: ignore[attr-defined]
    database_module._engine = None  # type: ignore[attr-defined]
    database_module._SessionLocal = None  # type: ignore[attr-defined]


def test_contradiction_seeds_repair_range_columns_and_merge_payloads(
    tmp_path, monkeypatch
) -> None:
    """Ensure contradiction seeds handle legacy schemas and mixed payload sources."""

    seed_dir = tmp_path / "seeds"
    seed_dir.mkdir()

    _write_seed(
        seed_dir / "contradictions.json",
        [
            {
                "osis_a": "Gen.1.1",
                "osis_b": "Gen.1.2",
                "summary": "json entry",
                "source": "Test Source",
                "tags": ["one", "two"],
                "weight": 2,
                "perspective": "Skeptical",
            }
        ],
    )
    _write_seed(
        seed_dir / "contradictions_additional.json",
        [
            {
                "osis_a": "Gen.1.3",
                "osis_b": "Gen.1.4",
                "summary": "additional entry",
                "source": "Another",
                "tags": "solo",
            }
        ],
    )
    (seed_dir / "contradictions_catalog.yaml").write_text(
        textwrap.dedent(
            """
            alpha:
              osis_a: Gen.1.5
              osis_b: Gen.1.6
              summary: catalog entry
              perspective: Analytical
              weight: 0.75
              tags:
                - curated
                - null
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(seeds, "SEED_ROOT", seed_dir)

    database_path = tmp_path / "legacy-contradictions.sqlite"
    engine = create_engine(f"sqlite:///{database_path}", future=True)

    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                """
                CREATE TABLE contradiction_seeds (
                    id TEXT PRIMARY KEY,
                    osis_a TEXT NOT NULL,
                    osis_b TEXT NOT NULL,
                    summary TEXT,
                    source TEXT,
                    tags TEXT,
                    weight FLOAT NOT NULL DEFAULT 1.0,
                    perspective TEXT,
                    created_at TIMESTAMP NOT NULL
                )
                """
            )

        with Session(engine) as session:
            seeds.seed_contradiction_claims(session)

        with engine.connect() as connection:
            column_names = {
                row[1]
                for row in connection.exec_driver_sql(
                    "PRAGMA table_info('contradiction_seeds')"
                )
            }
            assert {
                "start_verse_id_a",
                "end_verse_id_a",
                "start_verse_id",
                "end_verse_id",
                "start_verse_id_b",
                "end_verse_id_b",
            }.issubset(column_names)

        expected_ids = {
            "primary": str(
                seeds.uuid5(
                    seeds.CONTRADICTION_NAMESPACE,
                    "|".join(
                        [
                            "gen.1.1",
                            "gen.1.2",
                            "test source",
                            "skeptical",
                        ]
                    ),
                )
            ),
            "additional": str(
                seeds.uuid5(
                    seeds.CONTRADICTION_NAMESPACE,
                    "|".join(
                        [
                            "gen.1.3",
                            "gen.1.4",
                            "another",
                            "skeptical",
                        ]
                    ),
                )
            ),
            "catalog": str(
                seeds.uuid5(
                    seeds.CONTRADICTION_NAMESPACE,
                    "|".join(
                        [
                            "gen.1.5",
                            "gen.1.6",
                            "community",
                            "analytical",
                        ]
                    ),
                )
            ),
        }

        with Session(engine) as session:
            records = {
                record.id: record
                for record in session.scalars(select(ContradictionSeed))
            }

        assert set(records) == set(expected_ids.values())

        primary = records[expected_ids["primary"]]
        assert primary.source == "Test Source"
        assert primary.perspective == "skeptical"
        assert primary.tags == ["one", "two"]
        assert primary.weight == 2.0
        assert primary.start_verse_id_a == primary.start_verse_id
        assert primary.end_verse_id_a == primary.end_verse_id

        additional = records[expected_ids["additional"]]
        assert additional.perspective == "skeptical"
        assert additional.tags == ["solo"]
        assert additional.weight == 1.0
        assert additional.start_verse_id_b is not None
        assert additional.end_verse_id_b is not None

        catalog = records[expected_ids["catalog"]]
        assert catalog.source == "community"
        assert catalog.perspective == "analytical"
        assert catalog.tags == ["curated"]
        assert catalog.weight == 0.75
        assert catalog.start_verse_id is not None
        assert catalog.start_verse_id_b is not None
    finally:
        engine.dispose()

