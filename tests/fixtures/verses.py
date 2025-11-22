"""Fixtures providing canonical verse graph data for tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import importlib.util
import pytest

VERSE_DEPENDENCIES_AVAILABLE = True
VERSE_IMPORT_ERROR: Exception | None = None

try:  # pragma: no cover - optional dependency wiring
    theo_spec = importlib.util.find_spec("theo")
    if theo_spec is None:
        raise ModuleNotFoundError("verse graph dependencies unavailable")
except (ModuleNotFoundError, ImportError) as exc:  # pragma: no cover - dependency missing
    VERSE_DEPENDENCIES_AVAILABLE = False
    VERSE_IMPORT_ERROR = exc
    CommentarySeedRecord = None  # type: ignore[assignment]
    PairSeedRecord = None  # type: ignore[assignment]
    VerseSeedRelationships = None  # type: ignore[assignment]
    Passage = None  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover - typing only
    from theo.infrastructure.api.app.db.verse_graph import VerseSeedRelationships as VerseSeedRelationshipsType
else:  # pragma: no cover - runtime fallback
    VerseSeedRelationshipsType = object


def _require_dependencies() -> None:
    if not VERSE_DEPENDENCIES_AVAILABLE:
        pytest.skip(f"verse graph dependencies unavailable: {VERSE_IMPORT_ERROR}")


@pytest.fixture()
def verse_graph_passage():
    """Return a representative passage record for verse graph tests."""

    _require_dependencies()

    from theo.infrastructure.api.app.models.base import Passage

    return Passage(
        id="passage-1",
        document_id="doc-1",
        text="In the beginning was the Word",
        osis_ref="John.1.1",
        page_no=1,
        t_start=0.0,
        t_end=5.0,
        meta={
            "source_type": "sermon",
            "collection": "Advent Series",
            "authors": ["John Doe"],
            "document_title": "Incarnation Homily",
        },
    )


@pytest.fixture()
def verse_graph_mention(verse_graph_passage):
    """Expose a mention object wrapping the canonical passage."""

    return SimpleNamespace(passage=verse_graph_passage, context_snippet="Snippet text")


@pytest.fixture()
def verse_seed_relationships() -> VerseSeedRelationshipsType:
    """Provide canonical seed relationships used by verse graph tests."""

    _require_dependencies()

    from theo.infrastructure.api.app.db.verse_graph import (
        CommentarySeedRecord,
        PairSeedRecord,
        VerseSeedRelationships,
    )

    return VerseSeedRelationships(
        contradictions=[
            PairSeedRecord(
                id="ctr-1",
                osis_a="John.1.1",
                osis_b="Gen.1.1",
                summary="Apparent contradiction",
                source="Source A",
                tags=["tension"],
                weight=0.3,
                perspective="skeptical",
            )
        ],
        harmonies=[
            PairSeedRecord(
                id="harm-1",
                osis_a="Gen.1.1",
                osis_b="John.1.1",
                summary="Canonical harmony",
                source="Source B",
                tags=["unity"],
                weight=0.8,
                perspective="apologetic",
            )
        ],
        commentaries=[
            CommentarySeedRecord(
                id="comm-1",
                osis="John.1.1",
                title="Patristic reflection",
                excerpt="A commentary excerpt",
                source="Origen",
                tags=["christology"],
                perspective="neutral",
            )
        ],
    )
