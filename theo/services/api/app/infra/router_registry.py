"""Default router registrations for Theo's API infrastructure layer."""

from __future__ import annotations

# GraphQL support relies on optional dependencies (strawberry, etc.). When the
# dependency stack is incomplete we still want the remainder of the API to
# function – notably for unit/integration tests that exercise only REST routes.
# Import lazily and degrade gracefully so ``create_app`` can succeed even when
# GraphQL extras are not installed.
try:  # pragma: no cover - exercised indirectly via optional import handling
    from ..graphql.router import router as graphql_router
except Exception:  # pragma: no cover - import failure logged via registration skip
    graphql_router = None

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
    notebooks,
    realtime,
    research,
    search,
    trails,
    transcripts,
    verses,
)
from .registry import RouterRegistration, register_router

_DEFAULT_REGISTRATIONS: list[RouterRegistration] = []

if graphql_router is not None:
    _DEFAULT_REGISTRATIONS.append(
        RouterRegistration(
            router=graphql_router,
            prefix=None,
            tags=("graphql",),
            requires_security=False,
        )
    )

_DEFAULT_REGISTRATIONS.extend(
    [
        RouterRegistration(router=ingest.router, prefix="/ingest", tags=("ingest",)),
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
    ]
)

try:
    from ..routes import jobs  # noqa: WPS433 - optional dependency guard
except Exception:  # pragma: no cover - exercised when Celery extras absent
    jobs = None
else:
    _DEFAULT_REGISTRATIONS.append(
        RouterRegistration(router=jobs.router, prefix="/jobs", tags=("jobs",))
    )

for _registration in _DEFAULT_REGISTRATIONS:
    register_router(_registration)

__all__ = ["_DEFAULT_REGISTRATIONS"]
