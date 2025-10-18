"""Lookup helpers for geographic reference data."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Iterable

import pythonbible as pb
from sqlalchemy import case, func, select, true
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from theo.application.facades.settings_store import load_setting
from theo.adapters.persistence.models import (
    GeoAncientPlace,
    GeoGeometry,
    GeoModernLocation,
    GeoPlaceVerse,
)
from theo.domain.research.osis import format_osis, osis_to_readable
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


def _normalize(value: str) -> str:
    return value.casefold().strip()


def _location_aliases(location: GeoModernLocation) -> list[str]:
    names = location.names
    aliases: list[str] = []
    if isinstance(names, list):
        for entry in names:
            label: str | None = None
            if isinstance(entry, dict):
                label = entry.get("name")
            elif isinstance(entry, str):
                label = entry
            if not label:
                continue
            if label != location.friendly_id and label not in aliases:
                aliases.append(label)
    return aliases


def _candidate_strings(location: GeoModernLocation) -> Iterable[str]:
    seen: set[str] = set()

    def _emit(value: str | None) -> Iterable[str]:
        if not value:
            return
        normalized = value.casefold()
        if normalized in seen:
            return
        seen.add(normalized)
        yield value

    yield from _emit(location.friendly_id)

    for alias in _location_aliases(location):
        yield from _emit(alias)

    search_terms = location.search_terms
    if isinstance(search_terms, list):
        for term in search_terms:
            if isinstance(term, str):
                yield from _emit(term)


def _fuzzy_score(query: str, candidate: str) -> float:
    if not candidate:
        return 0.0
    matcher = SequenceMatcher(a=query, b=candidate.casefold())
    return matcher.ratio()


def _build_geo_items(locations: Iterable[GeoModernLocation]) -> list[GeoPlaceItem]:
    items: list[GeoPlaceItem] = []
    for location in locations:
        aliases = _location_aliases(location)
        items.append(
            GeoPlaceItem(
                modern_id=location.modern_id,
                slug=location.modern_id,
                name=location.friendly_id,
                lat=location.latitude,
                lng=location.longitude,
                geom_kind=location.geom_kind,
                confidence=location.confidence,
                aliases=aliases or None,
                sources=location.raw.get("coordinates_source")
                if isinstance(location.raw, dict)
                else None,
            )
        )
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

    bind = session.get_bind()
    dialect_name = getattr(getattr(bind, "dialect", None), "name", None)
    locations: list[GeoModernLocation]

    if dialect_name == "postgresql":
        ilike_pattern = f"%{normalized_query}%"
        alias_terms = func.unnest(
            func.coalesce(
                GeoModernLocation.search_terms,
                postgresql.array([func.lower(GeoModernLocation.friendly_id)]),
            )
        ).table_valued("term")

        alias_stats = (
            select(
                func.max(
                    func.greatest(
                        func.similarity(func.lower(alias_terms.c.term), normalized_query),
                        func.word_similarity(func.lower(alias_terms.c.term), normalized_query),
                    )
                ).label("alias_similarity"),
                func.max(
                    case(
                        (alias_terms.c.term.ilike(ilike_pattern), 1),
                        else_=0,
                    )
                ).label("alias_match"),
            )
            .select_from(alias_terms)
            .lateral("alias_stats")
        )

        friendly_similarity = func.greatest(
            func.similarity(func.lower(GeoModernLocation.friendly_id), normalized_query),
            func.word_similarity(func.lower(GeoModernLocation.friendly_id), normalized_query),
        )
        alias_similarity = func.coalesce(alias_stats.c.alias_similarity, 0.0)
        score_expr_base = func.greatest(friendly_similarity, alias_similarity)
        score_expr = score_expr_base.label("score")
        friendly_match = case(
            (GeoModernLocation.friendly_id.ilike(ilike_pattern), 1),
            else_=0,
        )
        alias_match = func.coalesce(alias_stats.c.alias_match, 0)
        match_rank_base = func.greatest(friendly_match, alias_match)

        stmt = (
            select(GeoModernLocation, score_expr, match_rank_base.label("match"))
            .join(alias_stats, true(), isouter=True)
            .where(
                (friendly_match > 0)
                | (alias_match > 0)
                | (score_expr_base > 0.0)
            )
            .order_by(
                match_rank_base.desc(),
                score_expr_base.desc(),
                GeoModernLocation.confidence.desc().nullslast(),
                GeoModernLocation.friendly_id,
            )
            .limit(limit)
        )

        try:
            results = session.execute(stmt).all()
        except (ProgrammingError, OperationalError):
            session.rollback()
        else:
            return _build_geo_items([row[0] for row in results])

    rows = session.query(GeoModernLocation).all()
    scored: list[_ScoredLocation] = []

    for location in rows:
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
    locations = [entry.location for entry in scored[:limit]]

    return _build_geo_items(locations)


def _normalize_osis(reference: str) -> list[str]:
    try:
        normalized = pb.get_references(osis_to_readable(reference))
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
