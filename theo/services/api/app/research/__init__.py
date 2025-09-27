"""Research data access helpers for scripture, cross-references, and notes."""

from .contradictions import search_contradictions
from .crossrefs import fetch_cross_references
from .fallacies import fallacy_detect
from .geo import lookup_geo_places
from .morphology import fetch_morphology
from .notes import (
    create_research_note,
    delete_research_note,
    get_notes_for_osis,
    update_research_note,
)
from .overview import build_reliability_overview
from .reports import report_build
from .scripture import fetch_passage
from .variants import variants_apparatus
from .historicity import historicity_search
from .dss_links import fetch_dss_links

__all__ = [
    "fetch_passage",
    "fetch_cross_references",
    "fetch_morphology",
    "create_research_note",
    "get_notes_for_osis",
    "update_research_note",
    "delete_research_note",
    "search_contradictions",
    "lookup_geo_places",
    "variants_apparatus",
    "historicity_search",
    "fallacy_detect",
    "report_build",
    "build_reliability_overview",
    "fetch_dss_links",
]
