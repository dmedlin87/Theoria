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

