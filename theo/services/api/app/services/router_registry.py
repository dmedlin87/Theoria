"""Default router registrations for the Theo Engine API."""

from __future__ import annotations

from ..graphql.router import router as graphql_router
from ..routes import (
    ai,
    analytics,
    creators,
    dashboard,
    discoveries,
    discoveries_v1,
    documents,
    export,
    features,
    ingest,
    jobs,
    notebooks,
    realtime,
    research,
    search,
    trails,
    transcripts,
    verses,
)
from .registry import RouterRegistration, register_router

_DEFAULT_REGISTRATIONS = (
    RouterRegistration(router=graphql_router, prefix="/graphql", tags=("graphql",)),
    RouterRegistration(router=ingest.router, prefix="/ingest", tags=("ingest",)),
    RouterRegistration(router=jobs.router, prefix="/jobs", tags=("jobs",)),
    RouterRegistration(router=search.router, prefix="/search", tags=("search",)),
    RouterRegistration(router=export.router, prefix="/export", tags=("export",)),
    RouterRegistration(router=export.api_router, prefix=None, tags=("export",)),
    RouterRegistration(router=verses.router, prefix="/verses", tags=("verses",)),
    RouterRegistration(
        router=discoveries_v1.router,
        prefix=None,
        tags=("discoveries-v1",),
        requires_security=False,
    ),
    RouterRegistration(
        router=discoveries.router,
        prefix="/discoveries/legacy",
        tags=("discoveries",),
    ),
    RouterRegistration(
        router=documents.router,
        prefix="/documents",
        tags=("documents",),
    ),
    RouterRegistration(
        router=features.router,
        prefix="/features",
        tags=("features",),
    ),
    RouterRegistration(
        router=research.router,
        prefix="/research",
        tags=("research",),
    ),
    RouterRegistration(
        router=creators.router,
        prefix="/creators",
        tags=("creators",),
    ),
    RouterRegistration(
        router=transcripts.router,
        prefix="/transcripts",
        tags=("transcripts",),
    ),
    RouterRegistration(router=trails.router, prefix="/trails", tags=("trails",)),
    RouterRegistration(
        router=notebooks.router,
        prefix="/notebooks",
        tags=("notebooks",),
    ),
    RouterRegistration(
        router=analytics.router,
        prefix="/analytics",
        tags=("analytics",),
    ),
    RouterRegistration(
        router=dashboard.router,
        prefix="/dashboard",
        tags=("dashboard",),
    ),
    RouterRegistration(router=ai.router, prefix="/ai", tags=("ai",)),
    RouterRegistration(router=ai.settings_router, prefix=None, tags=("ai-settings",)),
    RouterRegistration(
        router=realtime.router,
        prefix="/realtime",
        tags=("realtime",),
    ),
)

for _registration in _DEFAULT_REGISTRATIONS:
    register_router(_registration)

__all__ = ["_DEFAULT_REGISTRATIONS"]
