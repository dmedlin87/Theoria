"""Research data access helpers for scripture, cross-references, and notes."""

from .crossrefs import fetch_cross_references
from .contradictions import search_contradictions
from .geo import lookup_geo_places
from .morphology import fetch_morphology
from .scripture import fetch_passage
from .notes import (
    create_research_note,
    get_notes_for_osis,
)

__all__ = [
    "fetch_passage",
    "fetch_cross_references",
    "fetch_morphology",
    "create_research_note",
    "get_notes_for_osis",
    "search_contradictions",
    "lookup_geo_places",
]
