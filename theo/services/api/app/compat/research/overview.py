"""Compatibility helpers for reliability overview construction."""
from __future__ import annotations

from warnings import warn

from sqlalchemy.orm import Session

from theo.application.facades.research import get_research_service
from theo.domain.research import OverviewBullet, ReliabilityOverview

warn(
    "Importing from 'theo.services.api.app.research.overview' is deprecated; "
    "use 'theo.application.facades.research' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["OverviewBullet", "ReliabilityOverview", "build_reliability_overview"]


def build_reliability_overview(
    session: Session,
    osis: str,
    *,
    mode: str | None = None,
    note_limit: int = 3,
    manuscript_limit: int = 3,
) -> ReliabilityOverview:
    """Compatibility wrapper invoking the new research service."""

    service = get_research_service(session)
    return service.build_reliability_overview(
        osis,
        mode=mode,
        note_limit=note_limit,
        manuscript_limit=manuscript_limit,
    )
