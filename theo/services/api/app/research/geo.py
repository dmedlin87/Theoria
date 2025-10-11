"""Lookup helpers for geographic reference data."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Iterable

import pythonbible as pb
from sqlalchemy import case, func, text
from sqlalchemy.orm import Session

from ..core.settings_store import load_setting
from ..db.models import (
    GeoAncientPlace,
    GeoGeometry,
    GeoModernLocation,
    GeoPlaceVerse,
)
from ..ingest.osis import format_osis, _osis_to_readable
from ..models.research import (
    GeoAttribution,
    GeoLocationItem,
    GeoPlaceItem,
    GeoPlaceOccurrence,
    GeoVerseResponse,
)

_METADATA_KEY = "openbible_geo.metadata"
_SOURCE_URL = "https://www.openbible.info/geo"
_LICENSE = "CC-BY-4.0"


@dataclass(slots=True)
class _ScoredLocation:
    location: GeoModernLocation
    score: float


_TRGM_SUPPORT_CACHE: dict[int, bool] = {}


def _normalize(value: str) -> str:
    return value.casefold().strip()


def _extract_aliases_from_names(
    names: Any, friendly_id: str
) -> list[str]:  # pragma: no cover - exercised via callers
    aliases: list[str] = []
    if isinstance(names, list):
        friendly_norm = friendly_id.casefold()
        for entry in names:
            label: str | None = None
            if isinstance(entry, dict):
                value = entry.get("name")
                label = str(value) if value else None
            elif isinstance(entry, str):
                label = entry
            if not label:
                continue
            if label.casefold() == friendly_norm:
                continue
            if label not in aliases:
                aliases.append(label)
    return aliases


def _location_aliases(location: GeoModernLocation) -> list[str]:
    if location.search_aliases:
        friendly_norm = location.friendly_id.casefold()
        cleaned: list[str] = []
        for alias in location.search_aliases:
            if not alias:
                continue
            if alias.casefold() == friendly_norm:
                continue
            if alias not in cleaned:
                cleaned.append(alias)
        if cleaned:
            return cleaned
    names = location.names
    return _extract_aliases_from_names(names, location.friendly_id)


def _candidate_strings(location: GeoModernLocation) -> Iterable[str]:
    yield location.friendly_id
    for alias in _location_aliases(location):
        yield alias


def _fuzzy_score(query: str, candidate: str) -> float:
    if not candidate:
        return 0.0
    matcher = SequenceMatcher(a=query, b=candidate.casefold())
    return matcher.ratio()


def _database_supports_trigram(session: Session) -> bool:
    bind = session.get_bind()
    if bind is None:
        return False
    engine = getattr(bind, "engine", bind)
    key = id(engine)
    cached = _TRGM_SUPPORT_CACHE.get(key)
    if cached is not None:
        return cached

    dialect_name = getattr(engine.dialect, "name", "")
    if dialect_name != "postgresql":
        _TRGM_SUPPORT_CACHE[key] = False
        return False

    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
            )
            supported = result.scalar() is not None
    except Exception:  # pragma: no cover - safety net for missing extension
        supported = False

    _TRGM_SUPPORT_CACHE[key] = supported
    return supported


def _build_place_item(location: GeoModernLocation, aliases: list[str]) -> GeoPlaceItem:
    sources = None
    raw = location.raw
    if isinstance(raw, dict):
        source_info = raw.get("coordinates_source")
        if source_info:
            sources = source_info

    return GeoPlaceItem(
        modern_id=location.modern_id,
        slug=location.modern_id,
        name=location.friendly_id,
        lat=location.latitude,
        lng=location.longitude,
        geom_kind=location.geom_kind,
        confidence=location.confidence,
        aliases=aliases or None,
        sources=sources,
    )


def _lookup_geo_places_postgres(
    session: Session, normalized_query: str, limit: int
) -> list[GeoPlaceItem]:
    pattern = f"%{normalized_query}%"
    friendly_norm = func.lower(GeoModernLocation.friendly_id)
    alias_text = func.coalesce(
        func.array_to_string(GeoModernLocation.search_aliases, " "),
        "",
    )
    alias_norm = func.lower(alias_text)

    friendly_match = case((friendly_norm.like(pattern), 1.0), else_=0.0)
    alias_match = case((alias_norm.like(pattern), 1.0), else_=0.0)
    friendly_similarity = func.similarity(friendly_norm, normalized_query)
    alias_similarity = func.similarity(alias_norm, normalized_query)
    score_expr = func.greatest(
        friendly_match,
        alias_match,
        friendly_similarity,
        alias_similarity,
    )
    score = score_expr.label("score")

    rows = (
        session.query(GeoModernLocation, score)
        .filter(score_expr > 0)
        .order_by(
            score.desc(),
            func.coalesce(GeoModernLocation.confidence, 0.0).desc(),
            GeoModernLocation.friendly_id.asc(),
        )
        .limit(limit)
        .all()
    )

    items: list[GeoPlaceItem] = []
    for location, _ in rows:
        aliases = _location_aliases(location)
        items.append(_build_place_item(location, aliases))
    return items


def _lookup_geo_places_python(
    session: Session, normalized_query: str, limit: int
) -> list[GeoPlaceItem]:
    locations = session.query(GeoModernLocation).all()
    scored: list[_ScoredLocation] = []

    for location in locations:
        best_score = 0.0
        for candidate in _candidate_strings(location):
            candidate_norm = candidate.casefold()
            if normalized_query in candidate_norm:
                best_score = max(best_score, 1.0)
                break
            best_score = max(best_score, _fuzzy_score(normalized_query, candidate_norm))
        if best_score <= 0.0:
            continue
        scored.append(_ScoredLocation(location=location, score=best_score))

    scored.sort(
        key=lambda entry: (
            -entry.score,
            -(entry.location.confidence or 0.0),
            entry.location.friendly_id,
        )
    )

    items: list[GeoPlaceItem] = []
    for entry in scored[:limit]:
        location = entry.location
        aliases = _location_aliases(location)
        items.append(_build_place_item(location, aliases))
    return items


def lookup_geo_places(
    session: Session,
    *,
    query: str,
    limit: int = 10,
) -> list[GeoPlaceItem]:
    """Return ranked modern geographic entries for the given query."""

    normalized_query = _normalize(query)
    if not normalized_query:
        return []

    if _database_supports_trigram(session):
        return _lookup_geo_places_postgres(session, normalized_query, limit)
    return _lookup_geo_places_python(session, normalized_query, limit)


def _normalize_osis(reference: str) -> list[str]:
    try:
        normalized = pb.get_references(_osis_to_readable(reference))
    except Exception:  # pragma: no cover - pythonbible parsing safety net
        return [reference]
    if not normalized:
        return [reference]
    return [format_osis(ref) for ref in normalized]


def _modern_ids_for_place(raw: dict[str, Any]) -> list[str]:
    identifiers: set[str] = set()
    associations = raw.get("modern_associations")
    if isinstance(associations, dict):
        identifiers.update(str(key) for key in associations.keys())
    for identification in raw.get("identifications", []) or []:
        if not isinstance(identification, dict):
            continue
        target_id = identification.get("id")
        if isinstance(target_id, str) and target_id.startswith("m"):
            identifiers.add(target_id)
        for resolution in identification.get("resolutions", []) or []:
            if not isinstance(resolution, dict):
                continue
            basis = resolution.get("modern_basis_id")
            if isinstance(basis, str) and basis.startswith("m"):
                identifiers.add(basis)
    return sorted(identifiers)


def _geometry_ids_for_location(raw: dict[str, Any]) -> list[str]:
    geometry_ids: set[str] = set()
    for key in ("geometry_id", "precise_geometry_id"):
        value = raw.get(key)
        if isinstance(value, str):
            geometry_ids.add(value.split(".")[0])
    return sorted(geometry_ids)


def _build_geometry_map(
    session: Session, geometry_ids: set[str]
) -> dict[str, GeoGeometry]:
    if not geometry_ids:
        return {}
    records = (
        session.query(GeoGeometry)
        .filter(GeoGeometry.geometry_id.in_(list(geometry_ids)))
        .all()
    )
    return {record.geometry_id: record for record in records}


def places_for_osis(session: Session, osis: str) -> GeoVerseResponse:
    """Return ancient places and modern locations linked to ``osis``."""

    normalized_refs = _normalize_osis(osis)
    verse_rows = (
        session.query(GeoPlaceVerse)
        .join(GeoAncientPlace)
        .filter(GeoPlaceVerse.osis_ref.in_(normalized_refs))
        .all()
    )

    occurrences: dict[str, GeoPlaceOccurrence] = {}
    modern_ids: set[str] = set()
    requires_osm_credit = False

    for row in verse_rows:
        place = row.place
        if place is None:
            continue
        occurrence = occurrences.get(place.ancient_id)
        if occurrence is None:
            occurrence = GeoPlaceOccurrence(
                ancient_id=place.ancient_id,
                friendly_id=place.friendly_id,
                classification=place.classification,
                osis_refs=[row.osis_ref],
                raw=place.raw if isinstance(place.raw, dict) else None,
            )
            occurrences[place.ancient_id] = occurrence
        else:
            if row.osis_ref not in occurrence.osis_refs:
                occurrence.osis_refs.append(row.osis_ref)

        if isinstance(place.raw, dict):
            modern_ids.update(_modern_ids_for_place(place.raw))

    if not occurrences:
        metadata = load_setting(session, _METADATA_KEY, default=None)
        attribution = _build_attribution(metadata)
        if attribution:
            attribution = attribution.model_copy(update={"osm_required": False})
        return GeoVerseResponse(
            osis=normalized_refs[0] if normalized_refs else osis,
            places=[],
            attribution=attribution,
        )

    modern_records = (
        session.query(GeoModernLocation)
        .filter(GeoModernLocation.modern_id.in_(list(modern_ids)))
        .all()
        if modern_ids
        else []
    )
    modern_map = {record.modern_id: record for record in modern_records}

    geometry_ids: set[str] = set()
    for record in modern_records:
        if isinstance(record.raw, dict):
            geometry_ids.update(_geometry_ids_for_location(record.raw))
    geometry_map = _build_geometry_map(session, geometry_ids)

    for occurrence in occurrences.values():
        modern_list: list[GeoLocationItem] = []
        raw = occurrence.raw or {}
        for modern_id in _modern_ids_for_place(raw):
            location = modern_map.get(modern_id)
            if location is None:
                continue
            aliases = _location_aliases(location)
            geom: GeoGeometry | None = None
            for geom_id in _geometry_ids_for_location(
                location.raw if isinstance(location.raw, dict) else {}
            ):
                geom = geometry_map.get(geom_id)
                if geom:
                    break
            geometry_payload: dict[str, Any] | None = None
            if geom:
                geometry_payload = {
                    "geometry_id": geom.geometry_id,
                    "geom_type": geom.geom_type,
                    "geojson": geom.geojson,
                }
                requires_osm_credit = True
            modern_list.append(
                GeoLocationItem(
                    modern_id=location.modern_id,
                    friendly_id=location.friendly_id,
                    latitude=location.latitude,
                    longitude=location.longitude,
                    geom_kind=location.geom_kind,
                    confidence=location.confidence,
                    names=aliases or None,
                    geometry=geometry_payload,
                    raw=location.raw if isinstance(location.raw, dict) else None,
                )
            )
        occurrence.modern_locations = modern_list

    metadata = load_setting(session, _METADATA_KEY, default=None)
    attribution = _build_attribution(metadata)
    if attribution:
        attribution = attribution.model_copy(update={"osm_required": requires_osm_credit})
    return GeoVerseResponse(
        osis=normalized_refs[0] if normalized_refs else osis,
        places=sorted(occurrences.values(), key=lambda item: item.friendly_id.casefold()),
        attribution=attribution,
    )


def _build_attribution(metadata: Any) -> GeoAttribution | None:
    if not isinstance(metadata, dict):
        return GeoAttribution(
            source="OpenBible.info Bible-Geocoding",
            url=_SOURCE_URL,
            license=_LICENSE,
            commit_sha=None,
        )
    return GeoAttribution(
        source="OpenBible.info Bible-Geocoding",
        url=str(metadata.get("source_url") or _SOURCE_URL),
        license=str(metadata.get("license") or _LICENSE),
        commit_sha=metadata.get("commit_sha"),
    )
