"""Idempotent loader for the OpenBible.info geospatial dataset."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable

import pythonbible as pb
from sqlalchemy import delete, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from theo.services.api.app.core.settings_store import save_setting
from theo.services.api.app.db.models import (
    GeoAncientPlace,
    GeoGeometry,
    GeoImage,
    GeoModernLocation,
    GeoPlaceVerse,
)
from theo.services.api.app.ingest.osis import _osis_to_readable, format_osis

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = PROJECT_ROOT / "theo" / "data" / "providers" / "openbible-geo"
_METADATA_SETTING_KEY = "openbible_geo.metadata"
_LICENSE = "CC-BY-4.0"
_SOURCE_URL = "https://github.com/openbibleinfo/Bible-Geocoding-Data"

_SAMPLE_ANCIENT_PLACES = [
    {
        "ancient_id": "a-bethlehem",
        "friendly_id": "Bethlehem",
        "classification": "settlement",
        "raw": {
            "names": ["Bethlehem", "Bethlehem Ephrathah"],
            "modern_associations": {"bethlehem": {"confidence": 0.95}},
        },
    }
]

_SAMPLE_VERSE_LINKS = [
    {"ancient_id": "a-bethlehem", "osis_ref": "Mic.5.2"},
    {"ancient_id": "a-bethlehem", "osis_ref": "Matt.2.1"},
]

_SAMPLE_MODERN_LOCATIONS = [
    {
        "modern_id": "bethlehem",
        "friendly_id": "Bethlehem",
        "geom_kind": "point",
        "confidence": 0.95,
        "names": [
            {"name": "Bethlehem"},
            {"name": "Bethlehem Ephrathah"},
        ],
        "longitude": 35.2003,
        "latitude": 31.7054,
        "raw": {
            "names": [
                {"name": "Bethlehem"},
                {"name": "Bethlehem Ephrathah"},
            ],
            "coordinates_source": {"name": "Sample dataset"},
        },
    }
]


def _stream_json_lines(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        logger.warning("OpenBible geo payload missing: %s", path)
        return []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:  # pragma: no cover - defensive guard
                logger.exception("Failed to parse JSON line from %s", path)


def _normalize_osis(reference: str | None) -> list[str]:
    if not reference:
        return []
    try:
        normalized = pb.get_references(_osis_to_readable(reference))
    except Exception:  # pragma: no cover - pythonbible parsing guard
        return []
    if not normalized:
        return []
    return [format_osis(ref) for ref in normalized]


def _upsert_rows(
    session: Session,
    model: type[Any],
    rows: list[dict[str, Any]],
    conflict_columns: list[str],
) -> None:
    if not rows:
        return
    table = model.__table__
    bind = session.get_bind()
    dialect = bind.dialect.name if bind else ""
    update_columns = {
        col.name: col for col in table.c if col.name not in conflict_columns
    }

    if not update_columns:
        if dialect == "postgresql":
            stmt = pg_insert(table).values(rows)
            stmt = stmt.on_conflict_do_nothing(index_elements=conflict_columns)
            session.execute(stmt)
            return
        if dialect == "sqlite":
            stmt = sqlite_insert(table).values(rows)
            stmt = stmt.on_conflict_do_nothing(index_elements=conflict_columns)
            session.execute(stmt)
            return

    if dialect == "postgresql":
        stmt = pg_insert(table).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=conflict_columns,
            set_={key: stmt.excluded[key] for key in update_columns},
        )
        session.execute(stmt)
    elif dialect == "sqlite":
        stmt = sqlite_insert(table).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=conflict_columns,
            set_={key: stmt.excluded[key] for key in update_columns},
        )
        session.execute(stmt)
    else:  # pragma: no cover - fallback for unsupported dialects
        for row in rows:
            session.merge(model(**row))


def _parse_float(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):  # pragma: no cover - defensive guard
        return None


def _load_geometry_payload(
    entry: dict[str, Any], geometry_folder: Path
) -> dict[str, Any] | None:
    geojson_payload: dict[str, Any] = {}
    for key, value in entry.items():
        if not isinstance(value, str):
            continue
        if key.endswith("_geojson_file") or key == "geojson_file":
            target = geometry_folder / value
            if not target.exists():
                continue
            try:
                with target.open("r", encoding="utf-8") as handle:
                    geojson_payload[key] = json.load(handle)
            except json.JSONDecodeError:  # pragma: no cover - defensive guard
                logger.exception("Failed to parse GeoJSON file %s", target)
    return geojson_payload or None


def _detect_commit_sha(data_root: Path) -> str | None:
    git_executable = shutil.which("git")
    if not git_executable:
        logger.warning("Unable to resolve OpenBible geo commit SHA")
        return None

    try:
        result = subprocess.run(  # noqa: S603 - scoped git invocation for provenance
            [git_executable, "-C", str(data_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
    ):  # pragma: no cover - git missing
        logger.warning("Unable to resolve OpenBible geo commit SHA")
        return None
    return result.stdout.strip() or None


def _seed_sample_dataset(session: Session) -> None:
    logger.info("Seeding fallback OpenBible geo sample dataset")

    session.execute(delete(GeoPlaceVerse))
    session.execute(delete(GeoAncientPlace))
    session.execute(delete(GeoModernLocation))
    session.execute(delete(GeoGeometry))
    session.execute(delete(GeoImage))

    _upsert_rows(session, GeoAncientPlace, list(_SAMPLE_ANCIENT_PLACES), ["ancient_id"])
    _upsert_rows(
        session,
        GeoPlaceVerse,
        list(_SAMPLE_VERSE_LINKS),
        ["ancient_id", "osis_ref"],
    )
    _upsert_rows(
        session,
        GeoModernLocation,
        list(_SAMPLE_MODERN_LOCATIONS),
        ["modern_id"],
    )

    session.commit()

    metadata = {
        "id": "openbible_geo",
        "license": _LICENSE,
        "source_url": _SOURCE_URL,
        "commit_sha": "sample-dataset",
    }
    save_setting(session, _METADATA_SETTING_KEY, metadata)


def seed_openbible_geo(
    session: Session,
    *,
    data_root: Path | None = None,
    chunk_size: int = 500,
) -> None:
    """Load OpenBible geo metadata into the relational store."""

    root = data_root or DATA_ROOT
    data_folder = root / "data"
    geometry_folder = root / "geometry"

    if not data_folder.exists():
        logger.warning("OpenBible geo dataset not available at %s", data_folder)
        _seed_sample_dataset(session)
        return

    # 1) Ancient places and verse linkages
    ancient_entries = _stream_json_lines(data_folder / "ancient.jsonl")
    ancient_rows: list[dict[str, Any]] = []
    verse_rows: list[dict[str, Any]] = []
    seen_ancient: set[str] = set()

    for entry in ancient_entries:
        ancient_id = entry.get("id")
        friendly_id = entry.get("friendly_id")
        if not ancient_id or not friendly_id:
            continue
        seen_ancient.add(ancient_id)
        classification = entry.get("class") or entry.get("types")
        if isinstance(classification, list):
            classification_value = ",".join(str(item) for item in classification)
        else:
            classification_value = str(classification) if classification else None

        ancient_rows.append(
            {
                "ancient_id": ancient_id,
                "friendly_id": friendly_id,
                "classification": classification_value,
                "raw": entry,
            }
        )

        session.execute(
            delete(GeoPlaceVerse).where(GeoPlaceVerse.ancient_id == ancient_id)
        )

        for verse_entry in entry.get("verses", []):
            osis_values = _normalize_osis(verse_entry.get("osis"))
            for osis in osis_values:
                verse_rows.append({"ancient_id": ancient_id, "osis_ref": osis})
            if len(verse_rows) >= chunk_size:
                _upsert_rows(
                    session,
                    GeoPlaceVerse,
                    verse_rows,
                    ["ancient_id", "osis_ref"],
                )
                verse_rows.clear()

        if len(ancient_rows) >= chunk_size:
            _upsert_rows(session, GeoAncientPlace, ancient_rows, ["ancient_id"])
            ancient_rows.clear()

    if ancient_rows:
        _upsert_rows(session, GeoAncientPlace, ancient_rows, ["ancient_id"])
    if verse_rows:
        _upsert_rows(session, GeoPlaceVerse, verse_rows, ["ancient_id", "osis_ref"])

    if seen_ancient:
        session.execute(
            delete(GeoAncientPlace).where(
                ~GeoAncientPlace.ancient_id.in_(list(seen_ancient))
            )
        )

    # 2) Modern locations
    modern_entries = _stream_json_lines(data_folder / "modern.jsonl")
    location_rows: list[dict[str, Any]] = []
    seen_modern: set[str] = set()

    for entry in modern_entries:
        modern_id = entry.get("id")
        friendly_id = entry.get("friendly_id")
        if not modern_id or not friendly_id:
            continue
        seen_modern.add(modern_id)

        lon = lat = None
        lonlat = entry.get("lonlat")
        if isinstance(lonlat, str) and "," in lonlat:
            lon_str, lat_str = (segment.strip() for segment in lonlat.split(",", 1))
            lon = _parse_float(lon_str)
            lat = _parse_float(lat_str)

        location_rows.append(
            {
                "modern_id": modern_id,
                "friendly_id": friendly_id,
                "geom_kind": entry.get("geometry"),
                "confidence": _parse_float(entry.get("confidence")),
                "names": entry.get("names"),
                "longitude": lon,
                "latitude": lat,
                "raw": entry,
            }
        )
        if len(location_rows) >= chunk_size:
            _upsert_rows(session, GeoModernLocation, location_rows, ["modern_id"])
            location_rows.clear()

    if location_rows:
        _upsert_rows(session, GeoModernLocation, location_rows, ["modern_id"])

    if seen_modern:
        session.execute(
            delete(GeoModernLocation).where(
                ~GeoModernLocation.modern_id.in_(list(seen_modern))
            )
        )

    # 3) Geometry payloads
    geometry_entries = _stream_json_lines(data_folder / "geometry.jsonl")
    geometry_rows: list[dict[str, Any]] = []
    seen_geometry: set[str] = set()

    for entry in geometry_entries:
        geometry_id = entry.get("id")
        if not geometry_id:
            continue
        payload = _load_geometry_payload(entry, geometry_folder)
        if not payload:
            payload = {"metadata": entry}
        seen_geometry.add(geometry_id)
        geometry_rows.append(
            {
                "geometry_id": geometry_id,
                "geom_type": entry.get("geometry") or entry.get("format"),
                "geojson": payload,
            }
        )
        if len(geometry_rows) >= chunk_size:
            _upsert_rows(session, GeoGeometry, geometry_rows, ["geometry_id"])
            geometry_rows.clear()

    if geometry_rows:
        _upsert_rows(session, GeoGeometry, geometry_rows, ["geometry_id"])

    if seen_geometry:
        session.execute(
            delete(GeoGeometry).where(
                ~GeoGeometry.geometry_id.in_(list(seen_geometry))
            )
        )

    # 4) Image metadata
    image_entries = _stream_json_lines(data_folder / "image.jsonl")
    image_rows: list[dict[str, Any]] = []
    seen_images: set[tuple[str, str, str, str]] = set()

    for entry in image_entries:
        image_id = entry.get("id")
        thumbnails = entry.get("thumbnails") or {}
        descriptions = entry.get("descriptions") or {}
        if not image_id or not isinstance(descriptions, dict):
            continue
        for owner_id in descriptions:
            if not isinstance(owner_id, str):
                continue
            prefix = owner_id[:1]
            if prefix == "a":
                owner_kind = "ancient"
            elif prefix == "m":
                owner_kind = "modern"
            else:
                continue
            thumb_details = (
                thumbnails.get(owner_id) if isinstance(thumbnails, dict) else None
            )
            thumb_file = None
            if isinstance(thumb_details, dict):
                thumb_file = thumb_details.get("file")
            key = (
                image_id,
                owner_kind,
                owner_id,
                thumb_file or "__default__",
            )
            seen_images.add(key)
            image_rows.append(
                {
                    "image_id": image_id,
                    "owner_kind": owner_kind,
                    "owner_id": owner_id,
                    "thumb_file": thumb_file or "__default__",
                    "url": entry.get("url") or entry.get("file_url"),
                    "license": entry.get("license"),
                    "attribution": entry.get("credit") or entry.get("author"),
                }
            )
        if len(image_rows) >= chunk_size:
            _upsert_rows(
                session,
                GeoImage,
                image_rows,
                ["image_id", "owner_kind", "owner_id", "thumb_file"],
            )
            image_rows.clear()

    if image_rows:
        _upsert_rows(
            session,
            GeoImage,
            image_rows,
            ["image_id", "owner_kind", "owner_id", "thumb_file"],
        )

    if seen_images:
        session.execute(
            delete(GeoImage).where(
                ~tuple_(
                    GeoImage.image_id,
                    GeoImage.owner_kind,
                    GeoImage.owner_id,
                    GeoImage.thumb_file,
                ).in_(list(seen_images))
            )
        )

    session.commit()

    commit_sha = _detect_commit_sha(root)
    metadata = {
        "id": "openbible_geo",
        "license": _LICENSE,
        "source_url": _SOURCE_URL,
        "commit_sha": commit_sha,
    }
    save_setting(session, _METADATA_SETTING_KEY, metadata)
    logger.info(
        "Seeded OpenBible geo dataset%s",
        f" @ {commit_sha}" if commit_sha else "",
    )


__all__ = ["seed_openbible_geo"]
