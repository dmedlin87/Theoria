"""Regression tests for database seed loaders."""

from __future__ import annotations

import json
import sys
import logging
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.application.facades.database import Base
from theo.services.api.app.db import seeds
from theo.services.api.app.db.run_sql_migrations import run_sql_migrations
from theo.services.api.app.db.models import ContradictionSeed, GeoPlace


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


def test_seeders_skip_when_perspective_missing(caplog) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)

    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE contradiction_seeds (
                id VARCHAR PRIMARY KEY,
                osis_a VARCHAR NOT NULL,
                osis_b VARCHAR NOT NULL,
                summary TEXT,
                source VARCHAR,
                tags TEXT,
                weight FLOAT NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE harmony_seeds (
                id VARCHAR PRIMARY KEY,
                osis_a VARCHAR NOT NULL,
                osis_b VARCHAR NOT NULL,
                summary TEXT,
                source VARCHAR,
                tags TEXT,
                weight FLOAT NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE commentary_excerpt_seeds (
                id VARCHAR PRIMARY KEY,
                osis VARCHAR NOT NULL,
                title VARCHAR,
                excerpt TEXT NOT NULL,
                source VARCHAR,
                tags TEXT
            )
            """
        )

    caplog.clear()
    with Session(engine) as session, caplog.at_level(logging.WARNING):
        seeds.seed_contradiction_claims(session)
        seeds.seed_harmony_claims(session)
        seeds.seed_commentary_excerpts(session)
        assert not session.in_transaction()

    messages = [record.getMessage() for record in caplog.records]
    assert "Skipping contradiction seeds because 'perspective' column is missing" in messages
    assert "Skipping harmony seeds because 'perspective' column is missing" in messages
    assert "Skipping commentary excerpt seeds because 'perspective' column is missing" in messages


def test_seed_reference_data_provides_perspective_column(tmp_path, monkeypatch) -> None:
    """Seeding a new SQLite database should surface the perspective column."""

    seed_dir = tmp_path / "seeds"
    seed_dir.mkdir()

    contradictions_path = seed_dir / "contradictions.json"
    _write_seed(
        contradictions_path,
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

    monkeypatch.setattr(seeds, "SEED_ROOT", seed_dir)
    monkeypatch.setattr(seeds, "seed_openbible_geo", lambda session: None)

    database_path = tmp_path / "fresh.sqlite"
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
                weight FLOAT NOT NULL DEFAULT 1.0,
                perspective TEXT
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
                perspective TEXT,
                tags JSON
            )
            """
        )

    Base.metadata.create_all(engine)
    run_sql_migrations(engine)

    with Session(engine) as session:
        seeds.seed_reference_data(session)

    with Session(engine) as session:
        perspectives = session.execute(
            select(ContradictionSeed.perspective)
        ).scalars().all()
        assert perspectives == ["skeptical"]

