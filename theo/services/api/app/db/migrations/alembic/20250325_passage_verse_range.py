"""Add canonical verse range bounds to passages."""

from __future__ import annotations

import json
from typing import Any, Iterable, Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

from theo.services.api.app.ingest.osis import expand_osis_reference


revision = "20250325_passage_verse_range"
down_revision = None
branch_labels: tuple[str, ...] | None = None
depends_on: Iterable[str] | None = None


def _normalise_json(value: Any) -> Any:
    """Return a JSON-compatible structure for *value*."""

    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        try:
            return json.loads(value.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def _coerce_ids(raw: Any) -> list[int]:
    """Return integer verse identifiers extracted from *raw*."""

    if raw is None:
        return []
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="ignore")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
    else:
        parsed = raw
    result: list[int] = []
    if isinstance(parsed, Iterable):
        for item in parsed:
            try:
                value = int(item)
            except (TypeError, ValueError):
                continue
            result.append(value)
    return result


def _iter_candidate_ranges(rows: Sequence[sa.Row]) -> Iterable[tuple[str, int | None, int | None]]:
    """Yield ``(id, start, end)`` tuples for rows needing backfill."""

    for row in rows:
        mapping = row._mapping
        verse_ids: set[int] = set()
        verse_ids.update(_coerce_ids(mapping.get("osis_verse_ids")))

        osis_ref = mapping.get("osis_ref")
        if osis_ref:
            try:
                verse_ids.update(expand_osis_reference(osis_ref))
            except Exception:  # pragma: no cover - defensive guard
                pass

        meta_payload = _normalise_json(mapping.get("meta"))
        if isinstance(meta_payload, dict):
            refs = meta_payload.get("osis_refs_all")
            if isinstance(refs, list):
                for ref in refs:
                    if not ref:
                        continue
                    try:
                        verse_ids.update(expand_osis_reference(str(ref)))
                    except Exception:  # pragma: no cover - defensive guard
                        continue

        if verse_ids:
            yield mapping["id"], min(verse_ids), max(verse_ids)
        else:
            yield mapping["id"], None, None


def upgrade() -> None:
    op.add_column("passages", sa.Column("osis_start_verse_id", sa.Integer(), nullable=True))
    op.add_column("passages", sa.Column("osis_end_verse_id", sa.Integer(), nullable=True))
    op.create_index(
        "ix_passages_osis_verse_range",
        "passages",
        ["osis_start_verse_id", "osis_end_verse_id"],
    )

    bind = op.get_bind()
    session = Session(bind=bind)
    passages = sa.Table("passages", sa.MetaData(), autoload_with=bind)

    batch_size = 2000
    try:
        while True:
            rows = (
                session.execute(
                    sa.select(
                        passages.c.id,
                        passages.c.osis_ref,
                        passages.c.osis_verse_ids,
                        passages.c.meta,
                        passages.c.osis_start_verse_id,
                        passages.c.osis_end_verse_id,
                    )
                    .where(
                        sa.or_(
                            passages.c.osis_start_verse_id.is_(None),
                            passages.c.osis_end_verse_id.is_(None),
                        )
                    )
                    .order_by(passages.c.id)
                    .limit(batch_size)
                )
                .all()
            )
            if not rows:
                break

            updates: list[dict[str, int | None]] = []
            for passage_id, start, end in _iter_candidate_ranges(rows):
                updates.append(
                    {
                        "id": passage_id,
                        "osis_start_verse_id": start,
                        "osis_end_verse_id": end,
                    }
                )

            for payload in updates:
                session.execute(
                    passages.update()
                    .where(passages.c.id == payload["id"])
                    .values(
                        osis_start_verse_id=payload["osis_start_verse_id"],
                        osis_end_verse_id=payload["osis_end_verse_id"],
                    )
                )
            session.commit()
    finally:
        session.close()


def downgrade() -> None:
    op.drop_index("ix_passages_osis_verse_range", table_name="passages")
    op.drop_column("passages", "osis_end_verse_id")
    op.drop_column("passages", "osis_start_verse_id")
