"""Populate verse identifier ranges for seeded research datasets."""
"""Populate verse identifier ranges for seeded research datasets."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _configure_environment(database_url: str | None) -> None:
    os.environ.setdefault("THEO_DISABLE_AI_SETTINGS", "1")
    if database_url:
        os.environ["DATABASE_URL"] = database_url


def _load_settings():
    from theo.application.facades.settings import get_settings

    return get_settings()


def _ensure_models_loaded() -> None:
    import theo.services.api.app.db.models  # noqa: F401  (side-effect import)


def _verse_range(reference: str) -> tuple[int, int] | None:
    from theo.services.api.app.ingest.osis import expand_osis_reference

    verse_ids = expand_osis_reference(reference)
    if not verse_ids:
        return None
    return min(verse_ids), max(verse_ids)


def _update_pair_seed(seed, osis_attr: str, start_attr: str, end_attr: str) -> bool:
    osis_value = getattr(seed, osis_attr)
    if not osis_value:
        changed = getattr(seed, start_attr) is not None or getattr(seed, end_attr) is not None
        setattr(seed, start_attr, None)
        setattr(seed, end_attr, None)
        return changed

    verse_range = _verse_range(osis_value)
    if verse_range is None:
        if getattr(seed, start_attr) is None and getattr(seed, end_attr) is None:
            return False
        setattr(seed, start_attr, None)
        setattr(seed, end_attr, None)
        return True

    start_value, end_value = verse_range
    changed = False
    if getattr(seed, start_attr) != start_value:
        setattr(seed, start_attr, start_value)
        changed = True
    if getattr(seed, end_attr) != end_value:
        setattr(seed, end_attr, end_value)
        changed = True
    return changed


def _backfill(session: Session) -> tuple[int, int, int]:
    from theo.services.api.app.db.models import (
        CommentaryExcerptSeed,
        ContradictionSeed,
        HarmonySeed,
    )

    updated_contradictions = 0
    for seed in session.query(ContradictionSeed):
        changed = False
        if _update_pair_seed(seed, "osis_a", "start_verse_id", "end_verse_id"):
            changed = True
        if _update_pair_seed(seed, "osis_b", "start_verse_id_b", "end_verse_id_b"):
            changed = True
        if changed:
            updated_contradictions += 1

    updated_harmonies = 0
    for seed in session.query(HarmonySeed):
        changed = False
        if _update_pair_seed(seed, "osis_a", "start_verse_id", "end_verse_id"):
            changed = True
        if _update_pair_seed(seed, "osis_b", "start_verse_id_b", "end_verse_id_b"):
            changed = True
        if changed:
            updated_harmonies += 1

    updated_commentaries = 0
    for seed in session.query(CommentaryExcerptSeed):
        verse_range = _verse_range(seed.osis)
        if verse_range is None:
            changed = seed.start_verse_id is not None or seed.end_verse_id is not None
            seed.start_verse_id = None
            seed.end_verse_id = None
        else:
            start_value, end_value = verse_range
            changed = False
            if seed.start_verse_id != start_value:
                seed.start_verse_id = start_value
                changed = True
            if seed.end_verse_id != end_value:
                seed.end_verse_id = end_value
                changed = True
        if changed:
            updated_commentaries += 1

    session.commit()
    return updated_contradictions, updated_harmonies, updated_commentaries


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Populate start_verse_id/end_verse_id columns on seed tables using OSIS parsing."
        )
    )
    parser.add_argument(
        "--database-url",
        dest="database_url",
        help="Optional SQLAlchemy database URL override",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        default="INFO",
        help="Logging verbosity (DEBUG, INFO, WARNING, ERROR)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    _configure_environment(args.database_url)
    settings = _load_settings()

    from theo.application.facades.database import configure_engine

    engine = configure_engine(settings.database_url)
    _ensure_models_loaded()

    with Session(bind=engine) as session:
        updated = _backfill(session)

    logging.info(
        "Backfill complete (contradictions=%s, harmonies=%s, commentaries=%s)",
        *updated,
    )


if __name__ == "__main__":
    main()
