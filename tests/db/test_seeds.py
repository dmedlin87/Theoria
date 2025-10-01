"""Regression tests for database seed loaders."""

# ruff: noqa: E402
from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.core.database import Base
from theo.services.api.app.db import seeds
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

