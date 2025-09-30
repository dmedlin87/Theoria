import json
import sys
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

import pythonbible as pb
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

sys.path.append(str(Path(__file__).resolve().parents[2]))

from theo.services.api.app.core.database import Base
from theo.services.api.app.core.settings_store import load_setting
from theo.services.api.app.db.models import (
    GeoAncientPlace,
    GeoGeometry,
    GeoImage,
    GeoModernLocation,
    GeoPlaceVerse,
)
from theo.services.geo import seed_openbible_geo as seed_openbible_geo_public

seed_openbible_geo_module = import_module("theo.services.geo.seed_openbible_geo")
from theo.services.geo.seed_openbible_geo import (
    _detect_commit_sha,
    _load_geometry_payload,
    _normalize_osis,
    _parse_float,
    _seed_sample_dataset,
    _stream_json_lines,
    _upsert_rows,
)


@pytest.fixture()
def session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_stream_json_lines_missing_file(tmp_path, caplog):
    caplog.set_level("WARNING")
    missing_path = tmp_path / "missing.jsonl"

    result = list(_stream_json_lines(missing_path))

    assert result == []
    assert "payload missing" in caplog.text


def test_stream_json_lines_reads_entries(tmp_path):
    payload_path = tmp_path / "payload.jsonl"
    payload_path.write_text("\n".join(["", json.dumps({"id": 1}), "", json.dumps({"id": 2})]), "utf-8")

    result = list(_stream_json_lines(payload_path))

    assert result == [{"id": 1}, {"id": 2}]


def test_normalize_osis_success(monkeypatch):
    normalized = [pb.NormalizedReference(pb.Book.MICAH, 5, 2, 5, 2, None)]

    monkeypatch.setattr(
        seed_openbible_geo_module.pb,
        "get_references",
        lambda value: normalized,
    )

    assert _normalize_osis("Mic.5.2") == ["Mic.5.2"]


def test_normalize_osis_handles_errors(monkeypatch):
    monkeypatch.setattr(
        seed_openbible_geo_module.pb,
        "get_references",
        lambda value: (_ for _ in ()).throw(ValueError("boom")),
    )

    assert _normalize_osis("Mic.5.2") == []


def test_upsert_rows_sqlite(session):
    _upsert_rows(
        session,
        GeoAncientPlace,
        [
            {
                "ancient_id": "a-bethlehem",
                "friendly_id": "Bethlehem",
                "classification": "settlement",
                "raw": {"names": ["Bethlehem"]},
            }
        ],
        ["ancient_id"],
    )
    session.commit()

    record = session.get(GeoAncientPlace, "a-bethlehem")
    assert record and record.friendly_id == "Bethlehem"

    _upsert_rows(
        session,
        GeoAncientPlace,
        [
            {
                "ancient_id": "a-bethlehem",
                "friendly_id": "Bethlehem",
                "classification": "city",
                "raw": {"names": ["Bethlehem"]},
            }
        ],
        ["ancient_id"],
    )
    session.commit()

    record = session.get(GeoAncientPlace, "a-bethlehem")
    assert record and record.classification == "city"

    _upsert_rows(session, GeoAncientPlace, [], ["ancient_id"])


class DummyBind:
    def __init__(self, dialect_name: str):
        self.dialect = SimpleNamespace(name=dialect_name)


class DummySession:
    def __init__(self):
        self.merged = []

    def get_bind(self):
        return DummyBind("custom")

    def merge(self, instance):
        self.merged.append(instance)


def test_upsert_rows_fallback_merge():
    dummy_session = DummySession()

    _upsert_rows(
        dummy_session,
        GeoPlaceVerse,
        [
            {
                "ancient_id": "a-bethlehem",
                "osis_ref": "Mic.5.2",
            }
        ],
        ["ancient_id", "osis_ref"],
    )

    assert len(dummy_session.merged) == 1
    merged = dummy_session.merged[0]
    assert merged.ancient_id == "a-bethlehem"
    assert merged.osis_ref == "Mic.5.2"


def test_parse_float_variants():
    assert _parse_float(None) is None
    assert _parse_float(1) == 1.0
    assert _parse_float(1.5) == 1.5
    assert _parse_float("2.25") == pytest.approx(2.25)
    assert _parse_float("not-a-number") is None


def test_load_geometry_payload(tmp_path):
    geometry_folder = tmp_path
    (geometry_folder / "feature.json").write_text(json.dumps({"type": "Feature"}), "utf-8")
    entry = {
        "id": "geom-1",
        "metadata_geojson_file": "feature.json",
        "other": "value",
    }

    payload = _load_geometry_payload(entry, geometry_folder)

    assert payload == {"metadata_geojson_file": {"type": "Feature"}}


def test_detect_commit_sha_success(monkeypatch, tmp_path):
    def fake_run(args, check, capture_output, text):
        class Result:
            stdout = "abc123\n"

        return Result()

    monkeypatch.setattr(seed_openbible_geo_module.subprocess, "run", fake_run)

    sha = _detect_commit_sha(tmp_path)

    assert sha == "abc123"


def test_detect_commit_sha_failure(monkeypatch, tmp_path, caplog):
    caplog.set_level("WARNING")

    def fake_run(args, check, capture_output, text):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(seed_openbible_geo_module.subprocess, "run", fake_run)

    sha = _detect_commit_sha(tmp_path)

    assert sha is None
    assert "Unable to resolve" in caplog.text


def test_seed_sample_dataset(session, caplog):
    caplog.set_level("INFO")

    session.add(
        GeoAncientPlace(
            ancient_id="legacy",
            friendly_id="Legacy",
            classification="old",
            raw={"names": ["Legacy"]},
        )
    )
    session.add(
        GeoModernLocation(
            modern_id="legacy",
            friendly_id="Legacy",
            geom_kind="point",
            confidence=0.1,
            names=None,
            longitude=None,
            latitude=None,
            raw={"names": ["Legacy"]},
        )
    )
    session.commit()

    _seed_sample_dataset(session)

    place = session.get(GeoAncientPlace, "a-bethlehem")
    assert place and place.friendly_id == "Bethlehem"
    verses = list(session.scalars(select(GeoPlaceVerse)))
    assert any(verse.osis_ref == "Mic.5.2" for verse in verses)
    modern = session.get(GeoModernLocation, "bethlehem")
    assert modern and modern.longitude == pytest.approx(35.2003)

    metadata = load_setting(session, seed_openbible_geo_module._METADATA_SETTING_KEY)
    assert metadata and metadata["commit_sha"] == "sample-dataset"

    assert "Seeding fallback OpenBible geo sample dataset" in caplog.text


def _write_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row))
            handle.write("\n")


def test_seed_openbible_geo_full_dataset(session, tmp_path, monkeypatch):
    data_root = tmp_path
    data_dir = data_root / "data"
    geometry_dir = data_root / "geometry"
    data_dir.mkdir()
    geometry_dir.mkdir()

    _write_jsonl(
        data_dir / "ancient.jsonl",
        [
            {
                "id": "a-bethlehem",
                "friendly_id": "Bethlehem",
                "class": ["settlement"],
                "verses": [{"osis": "Mic.5.2"}],
            },
            {
                "id": "ignored",
                "friendly_id": "Ignored",
                "class": None,
                "verses": [],
            },
        ],
    )

    _write_jsonl(
        data_dir / "modern.jsonl",
        [
            {
                "id": "bethlehem",
                "friendly_id": "Bethlehem",
                "geometry": "point",
                "confidence": "0.95",
                "names": [{"name": "Bethlehem"}],
                "lonlat": "35.2003,31.7054",
                "raw": {"names": [{"name": "Bethlehem"}]},
            }
        ],
    )

    _write_jsonl(
        data_dir / "geometry.jsonl",
        [
            {
                "id": "geom-1",
                "geometry": "Polygon",
                "metadata_geojson_file": "feature.json",
            }
        ],
    )

    _write_jsonl(
        data_dir / "image.jsonl",
        [
            {
                "id": "img-1",
                "thumbnails": {
                    "a-bethlehem": {"file": "thumb.jpg"}
                },
                "descriptions": {"a-bethlehem": "Bethlehem"},
                "url": "https://example.com/image.jpg",
                "license": "CC",
                "credit": "Photographer",
            }
        ],
    )

    (geometry_dir / "feature.json").write_text(
        json.dumps({"type": "FeatureCollection", "features": []}),
        "utf-8",
    )

    session.add(
        GeoAncientPlace(
            ancient_id="remove-me",
            friendly_id="Remove",
            classification="obsolete",
            raw={"names": ["Remove"]},
        )
    )
    session.add(
        GeoModernLocation(
            modern_id="remove-me",
            friendly_id="Remove",
            geom_kind="point",
            confidence=None,
            names=None,
            longitude=None,
            latitude=None,
            raw={"names": ["Remove"]},
        )
    )
    session.add(
        GeoGeometry(
            geometry_id="obsolete",
            geom_type="Polygon",
            geojson={"type": "Feature"},
        )
    )
    session.add(
        GeoImage(
            image_id="obsolete",
            owner_kind="ancient",
            owner_id="remove-me",
            thumb_file="old-thumb",
            url=None,
            license=None,
            attribution=None,
        )
    )
    session.add(
        GeoPlaceVerse(
            ancient_id="a-bethlehem",
            osis_ref="Old.1.1",
        )
    )
    session.commit()

    monkeypatch.setattr(seed_openbible_geo_module, "_detect_commit_sha", lambda root: "abc123")

    seed_openbible_geo_public(session, data_root=data_root, chunk_size=1)

    place = session.get(GeoAncientPlace, "a-bethlehem")
    assert place and place.classification == "settlement"
    assert place.raw["friendly_id"] == "Bethlehem"
    verses = list(session.scalars(select(GeoPlaceVerse)))
    assert {verse.osis_ref for verse in verses} == {"Mic.5.2"}
    modern = session.get(GeoModernLocation, "bethlehem")
    assert modern and modern.longitude == pytest.approx(35.2003)
    geometry = session.get(GeoGeometry, "geom-1")
    assert geometry and geometry.geojson["metadata_geojson_file"]["type"] == "FeatureCollection"
    images = list(session.scalars(select(GeoImage)))
    assert len(images) == 1
    assert images[0].thumb_file == "thumb.jpg"

    assert session.get(GeoAncientPlace, "remove-me") is None
    assert session.get(GeoModernLocation, "remove-me") is None
    assert session.get(GeoGeometry, "obsolete") is None
    assert (
        session.get(
            GeoImage,
            {
                "image_id": "obsolete",
                "owner_kind": "ancient",
                "owner_id": "remove-me",
                "thumb_file": "old-thumb",
            },
        )
        is None
    )

    metadata = load_setting(session, seed_openbible_geo_module._METADATA_SETTING_KEY)
    assert metadata and metadata["commit_sha"] == "abc123"


def test_seed_openbible_geo_missing_dataset(session, tmp_path, monkeypatch):
    called = []

    def fake_seed_sample(target_session):
        called.append(True)

    monkeypatch.setattr(seed_openbible_geo_module, "_seed_sample_dataset", fake_seed_sample)
    monkeypatch.setattr(seed_openbible_geo_module, "_detect_commit_sha", lambda root: None)

    seed_openbible_geo_public(session, data_root=tmp_path)

    assert called == [True]
