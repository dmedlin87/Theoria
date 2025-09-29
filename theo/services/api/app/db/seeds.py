"""Idempotent seed loaders for research reference datasets."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable
from uuid import NAMESPACE_URL, uuid5

import yaml
from sqlalchemy import delete
from sqlalchemy.orm import Session

from theo.services.geo import seed_openbible_geo

from .models import CommentarySeed, ContradictionSeed, GeoPlace, HarmonySeed

PROJECT_ROOT = Path(__file__).resolve().parents[5]
SEED_ROOT = PROJECT_ROOT / "data" / "seeds"
CONTRADICTION_NAMESPACE = uuid5(NAMESPACE_URL, "theo-engine/contradictions")
HARMONY_NAMESPACE = uuid5(NAMESPACE_URL, "theo-engine/harmonies")
COMMENTARY_NAMESPACE = uuid5(NAMESPACE_URL, "theo-engine/commentaries")


def _load_seed_payload(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        if path.suffix.lower() in {".yaml", ".yml"}:
            payload = yaml.safe_load(handle) or []
        else:
            payload = json.load(handle)
    if isinstance(payload, dict):
        return list(payload.values())
    if isinstance(payload, list):
        return payload
    raise ValueError(f"Unsupported seed format for {path}")


def _load_seed_files(*paths: Path) -> list[dict]:
    records: list[dict] = []
    for path in paths:
        records.extend(_load_seed_payload(path))
    return records


def _coerce_list(value: object) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        result: list[str] = []
        for item in value:
            if item is None:
                continue
            result.append(str(item))
        return result or None
    return None


def seed_contradiction_claims(session: Session) -> None:
    """Load contradiction seeds into the database in an idempotent manner."""

    payload = _load_seed_files(
        SEED_ROOT / "contradictions.json",
        SEED_ROOT / "contradictions_additional.json",
    )
    if not payload:
        return

    seen_ids: set[str] = set()
    for entry in payload:
        osis_a = entry.get("osis_a")
        osis_b = entry.get("osis_b")
        if not osis_a or not osis_b:
            continue
        source = entry.get("source") or "community"
        perspective_raw = entry.get("perspective") or "skeptical"
        perspective = str(perspective_raw).strip().lower() or "skeptical"
        identifier = str(
            uuid5(
                CONTRADICTION_NAMESPACE,
                f"{str(osis_a).lower()}|{str(osis_b).lower()}|{source.lower()}|{perspective}",
            )
        )
        seen_ids.add(identifier)
        record = session.get(ContradictionSeed, identifier)
        tags = _coerce_list(entry.get("tags"))
        weight = float(entry.get("weight", 1.0))
        summary = entry.get("summary")

        if record is None:
            record = ContradictionSeed(
                id=identifier,
                osis_a=str(osis_a),
                osis_b=str(osis_b),
                summary=summary,
                source=source,
                tags=tags,
                weight=weight,
                perspective=perspective,
            )
            session.add(record)
        else:
            if record.osis_a != osis_a:
                record.osis_a = str(osis_a)
            if record.osis_b != osis_b:
                record.osis_b = str(osis_b)
            if record.summary != summary:
                record.summary = summary
            if record.source != source:
                record.source = source
            if record.tags != tags:
                record.tags = tags
            if record.weight != weight:
                record.weight = weight
            if record.perspective != perspective:
                record.perspective = perspective

    session.execute(
        delete(ContradictionSeed).where(~ContradictionSeed.id.in_(seen_ids))
    )
    session.commit()


def seed_harmony_claims(session: Session) -> None:
    """Load harmony seeds that foreground reconciliatory readings."""

    payload = _load_seed_files(SEED_ROOT / "harmonies.yaml")
    if not payload:
        return

    seen_ids: set[str] = set()
    for entry in payload:
        osis_a = entry.get("osis_a")
        osis_b = entry.get("osis_b")
        if not osis_a or not osis_b:
            continue
        source = entry.get("source") or "community"
        perspective_raw = entry.get("perspective") or "apologetic"
        perspective = str(perspective_raw).strip().lower() or "apologetic"
        identifier = str(
            uuid5(
                HARMONY_NAMESPACE,
                f"{str(osis_a).lower()}|{str(osis_b).lower()}|{source.lower()}|{perspective}",
            )
        )
        seen_ids.add(identifier)
        record = session.get(HarmonySeed, identifier)
        tags = _coerce_list(entry.get("tags"))
        weight = float(entry.get("weight", 1.0))
        summary = entry.get("summary")

        if record is None:
            record = HarmonySeed(
                id=identifier,
                osis_a=str(osis_a),
                osis_b=str(osis_b),
                summary=summary,
                source=source,
                tags=tags,
                weight=weight,
                perspective=perspective,
            )
            session.add(record)
        else:
            if record.osis_a != osis_a:
                record.osis_a = str(osis_a)
            if record.osis_b != osis_b:
                record.osis_b = str(osis_b)
            if record.summary != summary:
                record.summary = summary
            if record.source != source:
                record.source = source
            if record.tags != tags:
                record.tags = tags
            if record.weight != weight:
                record.weight = weight
            if record.perspective != perspective:
                record.perspective = perspective

    session.execute(delete(HarmonySeed).where(~HarmonySeed.id.in_(seen_ids)))
    session.commit()


def seed_commentary_excerpts(session: Session) -> None:
    """Load curated commentary excerpts from seed files."""

    payload = _load_seed_files(SEED_ROOT / "commentaries.yaml")
    if not payload:
        return

    seen_ids: set[str] = set()
    for entry in payload:
        osis = entry.get("osis")
        excerpt = entry.get("excerpt")
        if not osis or not excerpt:
            continue
        source = entry.get("source") or "community"
        perspective_raw = entry.get("perspective") or "neutral"
        perspective = str(perspective_raw).strip().lower() or "neutral"
        identifier = str(
            uuid5(
                COMMENTARY_NAMESPACE,
                f"{str(osis).lower()}|{source.lower()}|{perspective}|{str(excerpt).strip().lower()[:64]}",
            )
        )
        seen_ids.add(identifier)
        record = session.get(CommentarySeed, identifier)
        tags = _coerce_list(entry.get("tags"))
        title = entry.get("title")
        citation = entry.get("citation")
        cleaned_excerpt = str(excerpt).strip()

        if record is None:
            record = CommentarySeed(
                id=identifier,
                osis=str(osis),
                title=title,
                excerpt=cleaned_excerpt,
                source=source,
                citation=citation,
                tags=tags,
                perspective=perspective,
            )
            session.add(record)
        else:
            if record.osis != osis:
                record.osis = str(osis)
            if record.title != title:
                record.title = title
            if record.excerpt != cleaned_excerpt:
                record.excerpt = cleaned_excerpt
            if record.source != source:
                record.source = source
            if record.citation != citation:
                record.citation = citation
            if record.tags != tags:
                record.tags = tags
            if record.perspective != perspective:
                record.perspective = perspective

    session.execute(
        delete(CommentarySeed).where(~CommentarySeed.id.in_(seen_ids))
    )
    session.commit()


def seed_geo_places(session: Session) -> None:
    """Load geographical reference data."""

    seed_path = SEED_ROOT / "geo_places.json"
    if not seed_path.exists():
        return

    payload = _load_seed_payload(seed_path)
    seen_slugs: set[str] = set()
    for entry in payload:
        slug = entry.get("slug")
        name = entry.get("name")
        if not slug or not name:
            continue
        aliases = _coerce_list(entry.get("aliases"))
        sources = entry.get("sources")
        confidence = entry.get("confidence")
        lat = entry.get("lat")
        lng = entry.get("lng")

        seen_slugs.add(str(slug))
        record = session.get(GeoPlace, slug)
        if record is None:
            record = GeoPlace(
                slug=str(slug),
                name=str(name),
                lat=float(lat) if lat is not None else None,
                lng=float(lng) if lng is not None else None,
                confidence=float(confidence) if confidence is not None else None,
                aliases=aliases,
                sources=sources,
            )
            session.add(record)
        else:
            new_lat = float(lat) if lat is not None else None
            new_lng = float(lng) if lng is not None else None
            new_confidence = float(confidence) if confidence is not None else None

            changed = False
            if record.name != name:
                record.name = str(name)
                changed = True
            if record.lat != new_lat:
                record.lat = new_lat
                changed = True
            if record.lng != new_lng:
                record.lng = new_lng
                changed = True
            if record.confidence != new_confidence:
                record.confidence = new_confidence
                changed = True
            if record.aliases != aliases:
                record.aliases = aliases
                changed = True
            if record.sources != sources:
                record.sources = sources
                changed = True
            if changed:
                record.updated_at = datetime.now(UTC)

    session.execute(delete(GeoPlace).where(~GeoPlace.slug.in_(seen_slugs)))
    session.commit()


def seed_reference_data(session: Session) -> None:
    """Entry point for loading all bundled reference datasets."""

    seed_contradiction_claims(session)
    seed_harmony_claims(session)
    seed_commentary_excerpts(session)
    seed_geo_places(session)
    seed_openbible_geo(session)
