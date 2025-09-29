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

from .models import (
    CommentaryExcerptSeed,
    ContradictionSeed,
    GeoPlace,
    HarmonySeed,
)

PROJECT_ROOT = Path(__file__).resolve().parents[5]
SEED_ROOT = PROJECT_ROOT / "data" / "seeds"
CONTRADICTION_NAMESPACE = uuid5(NAMESPACE_URL, "theo-engine/contradictions")
HARMONY_NAMESPACE = uuid5(NAMESPACE_URL, "theo-engine/harmonies")
COMMENTARY_NAMESPACE = uuid5(NAMESPACE_URL, "theo-engine/commentary-excerpts")


def _load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        return list(payload.values())
    if isinstance(payload, list):
        return payload
    raise ValueError(f"Unsupported seed format for {path}")


def _load_yaml(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return list(payload.values())
    raise ValueError(f"Unsupported seed format for {path}")


def _load_seed_file(path: Path) -> list[dict]:
    if path.suffix.lower() in {".yml", ".yaml"}:
        return _load_yaml(path)
    if path.suffix.lower() == ".json":
        return _load_json(path)
    raise ValueError(f"Unsupported seed file extension: {path.suffix}")


def _load_seed_payload(*names: str) -> list[dict]:
    payload: list[dict] = []
    for name in names:
        entries = _load_seed_file(SEED_ROOT / name)
        if entries:
            payload.extend(entries)
    return payload


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

    payload = _load_seed_payload(
        "contradictions.json",
        "contradictions_extra.json",
    )
    seen_ids: set[str] = set()
    for entry in payload:
        osis_a = entry.get("osis_a")
        osis_b = entry.get("osis_b")
        if not osis_a or not osis_b:
            continue
        source = entry.get("source") or "community"
        perspective = (entry.get("perspective") or "skeptical").lower()
        identifier = str(
            uuid5(
                CONTRADICTION_NAMESPACE,
                "|".join(
                    [
                        str(osis_a).lower(),
                        str(osis_b).lower(),
                        source.lower(),
                        perspective,
                    ]
                ),
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
    """Load harmony seeds (apparent resolutions) into the database."""

    payload = _load_seed_payload("harmonies.json")
    if not payload:
        return

    seen_ids: set[str] = set()
    for entry in payload:
        osis_a = entry.get("osis_a")
        osis_b = entry.get("osis_b")
        if not osis_a or not osis_b:
            continue
        source = entry.get("source") or "community"
        perspective = (entry.get("perspective") or "apologetic").lower()
        identifier = str(
            uuid5(
                HARMONY_NAMESPACE,
                "|".join(
                    [
                        str(osis_a).lower(),
                        str(osis_b).lower(),
                        source.lower(),
                        perspective,
                    ]
                ),
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
            changed = False
            if record.osis_a != osis_a:
                record.osis_a = str(osis_a)
                changed = True
            if record.osis_b != osis_b:
                record.osis_b = str(osis_b)
                changed = True
            if record.summary != summary:
                record.summary = summary
                changed = True
            if record.source != source:
                record.source = source
                changed = True
            if record.tags != tags:
                record.tags = tags
                changed = True
            if record.weight != weight:
                record.weight = weight
                changed = True
            if record.perspective != perspective:
                record.perspective = perspective
                changed = True
            if changed:
                record.updated_at = datetime.now(UTC)

    session.execute(delete(HarmonySeed).where(~HarmonySeed.id.in_(seen_ids)))
    session.commit()


def seed_commentary_excerpts(session: Session) -> None:
    """Load curated commentary excerpts with perspective metadata."""

    payload = _load_seed_payload("commentary_excerpts.yaml")
    if not payload:
        return

    seen_ids: set[str] = set()
    for entry in payload:
        osis = entry.get("osis")
        excerpt = entry.get("excerpt")
        if not osis or not excerpt:
            continue
        title = entry.get("title")
        source = entry.get("source")
        citation = entry.get("citation")
        tradition = entry.get("tradition")
        perspective = entry.get("perspective")
        tags = _coerce_list(entry.get("tags"))

        identifier = str(
            uuid5(
                COMMENTARY_NAMESPACE,
                "|".join(
                    [
                        str(osis).lower(),
                        (title or excerpt[:50]).lower(),
                        (perspective or "neutral").lower(),
                    ]
                ),
            )
        )
        seen_ids.add(identifier)
        record = session.get(CommentaryExcerptSeed, identifier)

        if record is None:
            record = CommentaryExcerptSeed(
                id=identifier,
                osis=str(osis),
                title=title,
                excerpt=excerpt,
                source=source,
                citation=citation,
                tradition=tradition,
                perspective=perspective.lower() if perspective else None,
                tags=tags,
            )
            session.add(record)
        else:
            changed = False
            if record.osis != osis:
                record.osis = str(osis)
                changed = True
            if record.title != title:
                record.title = title
                changed = True
            if record.excerpt != excerpt:
                record.excerpt = excerpt
                changed = True
            if record.source != source:
                record.source = source
                changed = True
            if record.citation != citation:
                record.citation = citation
                changed = True
            if record.tradition != tradition:
                record.tradition = tradition
                changed = True
            normalized_perspective = perspective.lower() if perspective else None
            if record.perspective != normalized_perspective:
                record.perspective = normalized_perspective
                changed = True
            if record.tags != tags:
                record.tags = tags
                changed = True
            if changed:
                record.updated_at = datetime.now(UTC)

    session.execute(
        delete(CommentaryExcerptSeed).where(~CommentaryExcerptSeed.id.in_(seen_ids))
    )
    session.commit()


def seed_geo_places(session: Session) -> None:
    """Load geographical reference data."""

    seed_path = SEED_ROOT / "geo_places.json"
    if not seed_path.exists():
        return

    payload = _load_json(seed_path)
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
