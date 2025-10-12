"""Idempotent seed loaders for research reference datasets."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Iterable
from collections.abc import Callable
from uuid import NAMESPACE_URL, uuid5

import yaml
from sqlalchemy import Table, delete, inspect
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from theo.services.geo import seed_openbible_geo
from ..ingest.osis import expand_osis_reference

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
COMMENTARY_NAMESPACE = uuid5(NAMESPACE_URL, "theo-engine/commentaries")

logger = logging.getLogger(__name__)


def _load_structured(path: Path) -> list[dict]:
    if not path.exists():
        return []

    if path.suffix.lower() in {".yaml", ".yml"}:
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or []
    else:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    if isinstance(payload, dict):
        return list(payload.values())
    if isinstance(payload, list):
        return payload
    raise ValueError(f"Unsupported seed format for {path}")


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


def _verse_bounds(reference: str | None) -> tuple[int | None, int | None]:
    if not reference:
        return (None, None)
    verse_ids = expand_osis_reference(str(reference))
    if not verse_ids:
        return (None, None)
    return (min(verse_ids), max(verse_ids))


def _iter_seed_entries(*paths: Path) -> list[dict]:
    entries: list[dict] = []
    for path in paths:
        if not path.exists():
            continue
        entries.extend(_load_structured(path))
    return entries


def _verse_range(reference: str | None) -> tuple[int, int] | None:
    if not reference:
        return None
    verse_ids = expand_osis_reference(str(reference))
    if not verse_ids:
        return None
    return min(verse_ids), max(verse_ids)


def _assign_range(record, start_attr: str, end_attr: str, reference: str | None) -> bool:
    changed = False
    verse_range = _verse_range(reference)
    start_value = verse_range[0] if verse_range else None
    end_value = verse_range[1] if verse_range else None
    if getattr(record, start_attr, None) != start_value:
        setattr(record, start_attr, start_value)
        changed = True
    if getattr(record, end_attr, None) != end_value:
        setattr(record, end_attr, end_value)
        changed = True
    return changed


def _table_has_column(session: Session, table_name: str, column_name: str, *, schema: str | None = None) -> bool:
    """Check whether the bound database exposes ``column_name`` on ``table_name``."""

    bind = session.get_bind()
    if bind is None:
        return False

    dialect_name = getattr(getattr(bind, "dialect", None), "name", None)
    if dialect_name == "sqlite":
        connection: Connection | None = None
        should_close = False
        try:
            if isinstance(bind, Engine):
                connection = bind.connect()
                should_close = True
            else:
                connection = bind  # type: ignore[assignment]
            escaped_table = table_name.replace("'", "''")
            result = connection.exec_driver_sql(
                f"PRAGMA table_info('{escaped_table}')"
            )
            for row in result:
                if len(row) > 1 and row[1] == column_name:
                    return True
            return False
        except Exception:  # pragma: no cover - defensive: unexpected SQLite errors
            return False
        finally:
            if should_close and connection is not None:
                connection.close()

    inspector = inspect(bind)
    try:
        columns = inspector.get_columns(table_name, schema=schema)
    except Exception:  # pragma: no cover - defensive: DB might be mid-migration
        return False

    return any(column.get("name") == column_name for column in columns)


def _ensure_perspective_column(
    session: Session, table: Table, dataset_label: str
) -> bool:
    """Verify the ``perspective`` column exists before reading from ``table``."""

    if _table_has_column(session, table.name, "perspective", schema=table.schema):
        return True

    bind = session.get_bind()
    dialect_name = getattr(getattr(bind, "dialect", None), "name", None)
    if dialect_name == "sqlite" and bind is not None:
        connection: Connection | None = None
        should_close = False
        try:
            if isinstance(bind, Engine):
                connection = bind.connect()
                should_close = True
            else:
                connection = bind  # type: ignore[assignment]

            if connection is not None:
                statement = f'ALTER TABLE "{table.name}" ADD COLUMN perspective TEXT'
                try:
                    connection.exec_driver_sql(statement)
                except OperationalError as exc:  # pragma: no cover - duplicate column
                    message = str(getattr(exc, "orig", exc)).lower()
                    duplicate_indicators = ("duplicate column", "already exists")
                    if not any(indicator in message for indicator in duplicate_indicators):
                        logger.debug(
                            "Failed to backfill perspective column for %s seeds: %s",
                            dataset_label,
                            exc,
                        )
                except Exception as exc:  # pragma: no cover - defensive
                    logger.debug(
                        "Unexpected error while backfilling perspective column for %s seeds: %s",
                        dataset_label,
                        exc,
                    )
        finally:
            if should_close and connection is not None:
                connection.close()

        if _table_has_column(session, table.name, "perspective", schema=table.schema):
            return True

    session.rollback()
    logger.warning(
        "Skipping %s seeds because 'perspective' column is missing", dataset_label
    )
    return False


def _ensure_range_columns(
    session: Session, table: Table, dataset_label: str, columns: Iterable[str]
) -> bool:
    missing = [
        column
        for column in columns
        if not _table_has_column(session, table.name, column, schema=table.schema)
    ]
    if not missing:
        return True

    session.rollback()
    formatted = ", ".join(sorted(missing))
    logger.warning(
        "Skipping %s seeds because verse range column(s) are missing: %s",
        dataset_label,
        formatted,
    )
    return False


def _handle_missing_perspective_error(
    session: Session, dataset_label: str, exc: OperationalError
) -> bool:
    """Log and rollback when ``perspective`` column errors are encountered."""

    message = str(getattr(exc, "orig", exc)).lower()
    if "perspective" not in message:
        return False

    missing_indicators = (
        "no such column",
        "unknown column",
        "has no column named",
        "missing column",
        "column not found",
    )
    if not any(indicator in message for indicator in missing_indicators):
        return False

    session.rollback()
    logger.warning(
        "Skipping %s seeds because 'perspective' column is missing", dataset_label
    )
    return True


def _run_seed_with_perspective_guard(
    session: Session,
    seed_fn: Callable[[Session], None],
    dataset_label: str,
) -> None:
    """Execute *seed_fn* while gracefully handling missing perspective columns."""

    try:
        seed_fn(session)
    except OperationalError as exc:
        if _handle_missing_perspective_error(session, dataset_label, exc):
            return
        raise


def seed_contradiction_claims(session: Session) -> None:
    """Load contradiction seeds into the database in an idempotent manner."""

    table = ContradictionSeed.__table__
    if not _ensure_perspective_column(session, table, "contradiction"):
        return
    if not _ensure_range_columns(
        session,
        table,
        "contradiction",
        ("start_verse_id", "end_verse_id", "start_verse_id_b", "end_verse_id_b"),
    ):
        return

    payload = _iter_seed_entries(
        SEED_ROOT / "contradictions.json",
        SEED_ROOT / "contradictions_additional.json",
        SEED_ROOT / "contradictions_catalog.yaml",
    )
    seen_ids: set[str] = set()
    try:
        for entry in payload:
            osis_a = entry.get("osis_a")
            osis_b = entry.get("osis_b")
            if not osis_a or not osis_b:
                continue
            osis_a_value = str(osis_a)
            osis_b_value = str(osis_b)
            start_a, end_a = _verse_bounds(osis_a_value)
            start_b, end_b = _verse_bounds(osis_b_value)
            source = entry.get("source") or "community"
            perspective = (entry.get("perspective") or "skeptical").strip().lower()
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
            range_a = _verse_range(str(osis_a))
            range_b = _verse_range(str(osis_b))
            start_a = range_a[0] if range_a else None
            end_a = range_a[1] if range_a else None
            start_b = range_b[0] if range_b else None
            end_b = range_b[1] if range_b else None

            if record is None:
                record = ContradictionSeed(
                    id=identifier,
                    osis_a=osis_a_value,
                    osis_b=osis_b_value,
                    summary=summary,
                    source=source,
                    tags=tags,
                    weight=weight,
                    perspective=perspective,
                    start_verse_id_a=start_a,
                    end_verse_id_a=end_a,
                    start_verse_id=start_a,
                    end_verse_id=end_a,
                    start_verse_id_b=start_b,
                    end_verse_id_b=end_b,
                )
                session.add(record)
            else:
                if record.osis_a != osis_a_value:
                    record.osis_a = osis_a_value
                if record.osis_b != osis_b_value:
                    record.osis_b = osis_b_value
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
                if record.start_verse_id_a != start_a:
                    record.start_verse_id_a = start_a
                if record.end_verse_id_a != end_a:
                    record.end_verse_id_a = end_a
                if record.start_verse_id_b != start_b:
                    record.start_verse_id_b = start_b
                if record.end_verse_id_b != end_b:
                    record.end_verse_id_b = end_b
                _assign_range(record, "start_verse_id", "end_verse_id", str(osis_a))
                _assign_range(
                    record,
                    "start_verse_id_b",
                    "end_verse_id_b",
                    str(osis_b),
                )
    except OperationalError as exc:
        session.rollback()
        message = str(exc).lower()
        if "no such column" in message and "perspective" in message:
            logger.warning(
                "Skipping contradiction seeds because 'perspective' column is unavailable: %s",
                exc,
            )
            return
        raise

    if seen_ids:
        try:
            session.execute(
                delete(ContradictionSeed).where(~ContradictionSeed.id.in_(seen_ids))
            )
        except OperationalError as exc:
            if _handle_missing_perspective_error(session, "contradiction", exc):
                return
            raise
    try:
        session.commit()
    except OperationalError as exc:
        if _handle_missing_perspective_error(session, "contradiction", exc):
            return
        raise


def seed_harmony_claims(session: Session) -> None:
    """Load harmony seeds from bundled YAML/JSON files."""

    table = HarmonySeed.__table__
    if not _ensure_perspective_column(session, table, "harmony"):
        return
    if not _ensure_range_columns(
        session,
        table,
        "harmony",
        ("start_verse_id", "end_verse_id", "start_verse_id_b", "end_verse_id_b"),
    ):
        return

    payload = _iter_seed_entries(
        SEED_ROOT / "harmonies.yaml",
        SEED_ROOT / "harmonies.json",
        SEED_ROOT / "harmonies_additional.yaml",
    )
    if not payload:
        return

    seen_ids: set[str] = set()
    for entry in payload:
        osis_a = entry.get("osis_a")
        osis_b = entry.get("osis_b")
        summary = entry.get("summary")
        if not osis_a or not osis_b or not summary:
            continue
        osis_a_value = str(osis_a)
        osis_b_value = str(osis_b)
        start_a, end_a = _verse_bounds(osis_a_value)
        start_b, end_b = _verse_bounds(osis_b_value)
        source = entry.get("source") or "community"
        perspective = (entry.get("perspective") or "apologetic").strip().lower()
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
        range_a = _verse_range(str(osis_a))
        range_b = _verse_range(str(osis_b))
        start_a = range_a[0] if range_a else None
        end_a = range_a[1] if range_a else None
        start_b = range_b[0] if range_b else None
        end_b = range_b[1] if range_b else None

        if record is None:
            record = HarmonySeed(
                id=identifier,
                osis_a=osis_a_value,
                osis_b=osis_b_value,
                summary=summary,
                source=source,
                tags=tags,
                weight=weight,
                perspective=perspective,
                start_verse_id_a=start_a,
                end_verse_id_a=end_a,
                start_verse_id=start_a,
                end_verse_id=end_a,
                start_verse_id_b=start_b,
                end_verse_id_b=end_b,
            )
            session.add(record)
        else:
            updated = False
            if record.osis_a != osis_a_value:
                record.osis_a = osis_a_value
                updated = True
            if record.osis_b != osis_b_value:
                record.osis_b = osis_b_value
                updated = True
            if record.summary != summary:
                record.summary = summary
                updated = True
            if record.source != source:
                record.source = source
                updated = True
            if record.tags != tags:
                record.tags = tags
                updated = True
            if record.weight != weight:
                record.weight = weight
                updated = True
            if record.perspective != perspective:
                record.perspective = perspective
                updated = True
            if record.start_verse_id_a != start_a:
                record.start_verse_id_a = start_a
                updated = True
            if record.end_verse_id_a != end_a:
                record.end_verse_id_a = end_a
                updated = True
            if record.start_verse_id_b != start_b:
                record.start_verse_id_b = start_b
                updated = True
            if record.end_verse_id_b != end_b:
                record.end_verse_id_b = end_b
            if _assign_range(record, "start_verse_id", "end_verse_id", str(osis_a)):
                updated = True
            if _assign_range(
                record,
                "start_verse_id_b",
                "end_verse_id_b",
                str(osis_b),
            ):
                updated = True
            if updated:
                record.updated_at = datetime.now(UTC)

    if seen_ids:
        try:
            session.execute(delete(HarmonySeed).where(~HarmonySeed.id.in_(seen_ids)))
        except OperationalError as exc:
            if _handle_missing_perspective_error(session, "harmony", exc):
                return
            raise
    try:
        session.commit()
    except OperationalError as exc:
        if _handle_missing_perspective_error(session, "harmony", exc):
            return
        raise


def seed_commentary_excerpts(session: Session) -> None:
    """Seed curated commentary excerpts into the catalogue."""

    table = CommentaryExcerptSeed.__table__
    if not _ensure_perspective_column(session, table, "commentary excerpt"):
        return
    if not _ensure_range_columns(
        session,
        table,
        "commentary excerpt",
        ("start_verse_id", "end_verse_id"),
    ):
        return

    payload = _iter_seed_entries(
        SEED_ROOT / "commentaries.yaml",
        SEED_ROOT / "commentaries.json",
        SEED_ROOT / "commentaries_additional.yaml",
    )
    if not payload:
        return

    seen_ids: set[str] = set()
    for entry in payload:
        osis = entry.get("osis")
        excerpt = entry.get("excerpt")
        if not osis or not excerpt:
            continue
        osis_value = str(osis)
        start_verse_id, end_verse_id = _verse_bounds(osis_value)
        source = entry.get("source") or "community"
        perspective = (entry.get("perspective") or "neutral").strip().lower()
        identifier = str(
            uuid5(
                COMMENTARY_NAMESPACE,
                "|".join([str(osis).lower(), source.lower(), perspective, excerpt[:64].lower()]),
            )
        )
        seen_ids.add(identifier)
        record = session.get(CommentaryExcerptSeed, identifier)
        tags = _coerce_list(entry.get("tags"))
        title = entry.get("title")
        verse_range = _verse_range(str(osis))
        start_value = verse_range[0] if verse_range else None
        end_value = verse_range[1] if verse_range else None

        if record is None:
            record = CommentaryExcerptSeed(
                id=identifier,
                osis=osis_value,
                title=title,
                excerpt=excerpt,
                source=source,
                perspective=perspective,
                tags=tags,
                start_verse_id=start_value,
                end_verse_id=end_value,
            )
            session.add(record)
        else:
            updated = False
            if record.osis != osis_value:
                record.osis = osis_value
                updated = True
            if record.title != title:
                record.title = title
                updated = True
            if record.excerpt != excerpt:
                record.excerpt = excerpt
                updated = True
            if record.source != source:
                record.source = source
                updated = True
            if record.perspective != perspective:
                record.perspective = perspective
                updated = True
            if record.tags != tags:
                record.tags = tags
                updated = True
            if record.start_verse_id != start_verse_id:
                record.start_verse_id = start_verse_id
                updated = True
            if record.end_verse_id != end_verse_id:
                record.end_verse_id = end_verse_id
            if _assign_range(record, "start_verse_id", "end_verse_id", str(osis)):
                updated = True
            if updated:
                record.updated_at = datetime.now(UTC)

    if seen_ids:
        session.execute(
            delete(CommentaryExcerptSeed).where(~CommentaryExcerptSeed.id.in_(seen_ids))
        )
    session.commit()


def seed_geo_places(session: Session) -> None:
    """Load geographical reference data."""

    seed_path = SEED_ROOT / "geo_places.json"
    if not seed_path.exists():
        return

    payload = _load_structured(seed_path)
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


def _safe_seed(
    session: Session,
    loader: Callable[[Session], None],
    dataset_label: str,
) -> None:
    """Execute ``loader`` while downgrading missing perspective columns to warnings."""

    try:
        loader(session)
    except OperationalError as exc:
        if _handle_missing_perspective_error(session, dataset_label, exc):
            return
        raise


def seed_reference_data(session: Session) -> None:
    """Entry point for loading all bundled reference datasets."""

    perspective_guarded_seeders = (
        (ContradictionSeed.__table__, seed_contradiction_claims, "contradiction"),
        (HarmonySeed.__table__, seed_harmony_claims, "harmony"),
        (
            CommentaryExcerptSeed.__table__,
            seed_commentary_excerpts,
            "commentary excerpt",
        ),
    )

    for table, loader, label in perspective_guarded_seeders:
        if not _ensure_perspective_column(session, table, label):
            continue
        _safe_seed(session, loader, label)
        _run_seed_with_perspective_guard(session, loader, label)
    seed_geo_places(session)
    seed_openbible_geo(session)
