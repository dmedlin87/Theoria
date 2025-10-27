"""Backfill verse range metadata for seed tables."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from theo.infrastructure.api.app.ingest.osis import expand_osis_reference
from theo.infrastructure.api.app.persistence_models import (
    CommentaryExcerptSeed,
    ContradictionSeed,
    HarmonySeed,
)


def _range_bounds(reference: str | None) -> tuple[int | None, int | None]:
    if not reference:
        return (None, None)
    verse_ids = expand_osis_reference(reference)
    if not verse_ids:
        return (None, None)
    return (min(verse_ids), max(verse_ids))


def _bulk_backfill(
    session: Session,
    model: type[Any],
    columns: Iterable[tuple[str, str]],
    *,
    osis_columns: Iterable[str],
) -> None:
    osis_columns = list(osis_columns)
    column_pairs = list(columns)
    if not osis_columns:
        return

    stmt = select(model.id, *[getattr(model, column) for column in osis_columns])
    results = session.execute(stmt).all()
    if not results:
        return

    updates: list[dict[str, Any]] = []
    for row in results:
        record_id = row[0]
        values: dict[str, Any] = {"id": record_id}
        for (start_column, end_column), reference in zip(column_pairs, row[1:]):
            start, end = _range_bounds(reference)
            values[start_column] = start
            values[end_column] = end
        updates.append(values)

    if updates:
        session.bulk_update_mappings(model, updates)


def upgrade(*, session: Session, engine) -> None:  # pragma: no cover - executed via migration runner
    _bulk_backfill(
        session,
        ContradictionSeed,
        (
            ("start_verse_id_a", "end_verse_id_a"),
            ("start_verse_id_b", "end_verse_id_b"),
        ),
        osis_columns=("osis_a", "osis_b"),
    )
    _bulk_backfill(
        session,
        HarmonySeed,
        (
            ("start_verse_id_a", "end_verse_id_a"),
            ("start_verse_id_b", "end_verse_id_b"),
        ),
        osis_columns=("osis_a", "osis_b"),
    )
    _bulk_backfill(
        session,
        CommentaryExcerptSeed,
        (("start_verse_id", "end_verse_id"),),
        osis_columns=("osis",),
    )

    session.flush()
