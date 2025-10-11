from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import or_
from sqlalchemy.orm import Session

from theo.services.api.app.db.models import Passage
from theo.services.api.app.ingest.osis import canonical_verse_range

BATCH_SIZE = 500


def _normalise_ids(values: Sequence[object] | None) -> list[int]:
    normalised: list[int] = []
    if not values:
        return normalised
    for value in values:
        try:
            normalised.append(int(value))
        except (TypeError, ValueError):
            continue
    return normalised


def _reference_candidates(passage: Passage) -> list[str]:
    references: set[str] = set()
    if passage.osis_ref:
        references.add(passage.osis_ref)

    meta = passage.meta
    if isinstance(meta, dict):
        for key in (
            "primary_osis",
            "osis_refs_all",
            "osis_refs_detected",
            "osis_refs_hints",
            "osis_refs_unmatched",
        ):
            value = meta.get(key)
            if isinstance(value, str):
                if value:
                    references.add(value)
            elif isinstance(value, (list, tuple, set)):
                for item in value:
                    if item:
                        references.add(str(item))

    return sorted(ref for ref in references if ref)


def _determine_range(passage: Passage) -> tuple[int | None, int | None]:
    ids = _normalise_ids(passage.osis_verse_ids)
    if ids:
        return min(ids), max(ids)

    references = _reference_candidates(passage)
    _, start, end = canonical_verse_range(references)
    if start is not None and end is not None:
        return start, end

    return None, None


def apply(session: Session) -> None:
    """Populate ``Passage`` records with canonical verse range metadata."""

    last_id: str | None = None

    while True:
        query = (
            session.query(Passage)
            .filter(
                or_(
                    Passage.osis_start_verse_id.is_(None),
                    Passage.osis_end_verse_id.is_(None),
                )
            )
            .order_by(Passage.id)
            .limit(BATCH_SIZE)
        )
        if last_id is not None:
            query = query.filter(Passage.id > last_id)

        batch = query.all()
        if not batch:
            break

        last_id = batch[-1].id
        batch_changed = False

        for passage in batch:
            start, end = _determine_range(passage)
            if start is not None and passage.osis_start_verse_id != start:
                passage.osis_start_verse_id = start
                batch_changed = True
            if end is not None and passage.osis_end_verse_id != end:
                passage.osis_end_verse_id = end
                batch_changed = True

        if batch_changed:
            session.flush()
