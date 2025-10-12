"""Compatibility helpers for research report generation."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from warnings import warn

from sqlalchemy.orm import Session

from theo.application.facades.research import get_research_service
from theo.application.research import ReportSection, ResearchReport

warn(
    "Importing from 'theo.services.api.app.research.reports' is deprecated; "
    "use 'theo.application.research' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["ReportSection", "ResearchReport", "report_build"]


def report_build(
    session: Session,
    osis: str,
    *,
    stance: str,
    claims: Iterable[Mapping[str, object]] | None = None,
    historicity_query: str | None = None,
    narrative_text: str | None = None,
    include_fallacies: bool = False,
    variants_limit: int | None = None,
    citations_limit: int = 5,
    min_fallacy_confidence: float = 0.0,
) -> ResearchReport:
    """Compatibility wrapper invoking the new research service."""

    service = get_research_service(session)
    return service.report_build(
        osis,
        stance=stance,
        claims=claims,
        historicity_query=historicity_query,
        narrative_text=narrative_text,
        include_fallacies=include_fallacies,
        variants_limit=variants_limit,
        citations_limit=citations_limit,
        min_fallacy_confidence=min_fallacy_confidence,
    )
