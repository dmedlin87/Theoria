"""Route registration helpers for the API bootstrap."""

from __future__ import annotations

import importlib
import logging
from typing import Callable, Sequence

from fastapi import Depends, FastAPI
from fastapi.responses import PlainTextResponse

from ..routes import (  # noqa: F401  (ensure handlers register)
    ai,
    analytics,
    creators,
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
from ..infra.registry import RouterRegistration, iter_router_registrations
try:  # pragma: no cover - optional dependency guard
    from ..routes import jobs  # noqa: F401  (ensure handlers register)
except Exception:  # pragma: no cover - Celery extras not installed
    pass

logger = logging.getLogger(__name__)

GenerateLatestFn = Callable[[], bytes]
CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"
generate_latest: GenerateLatestFn | None = None

try:  # pragma: no cover - optional dependency
    prometheus_client = importlib.import_module("prometheus_client")
except ImportError:  # pragma: no cover - graceful degradation
    pass
else:
    CONTENT_TYPE_LATEST = str(prometheus_client.CONTENT_TYPE_LATEST)
    generate_latest = prometheus_client.generate_latest  # type: ignore[assignment]

__all__ = [
    "register_health_routes",
    "include_router_registrations",
    "register_metrics_endpoint",
    "mount_mcp",
    "get_router_registrations",
    "ROUTER_REGISTRATIONS",
]


def register_health_routes(app: FastAPI) -> None:
    """Register lightweight health-check endpoints."""

    @app.get("/health", tags=["diagnostics"], include_in_schema=False)
    async def healthcheck() -> dict[str, object]:
        from ..infra.health import get_health_service

        report = get_health_service().check()
        return report.to_summary()

    @app.get("/health/detail", tags=["diagnostics"], include_in_schema=False)
    async def healthcheck_detail() -> dict[str, object]:
        from ..infra.health import get_health_service

        report = get_health_service().check()
        return report.to_detail()


def include_router_registrations(
    app: FastAPI,
    *,
    security_dependencies: Sequence[Depends],
) -> None:
    """Attach routers declared in the shared registry."""

    for registration in iter_router_registrations():
        include_kwargs: dict[str, object] = {
            "router": registration.router,
            "tags": list(registration.tags),
        }
        if registration.prefix is not None:
            include_kwargs["prefix"] = registration.prefix
        if registration.requires_security:
            include_kwargs["dependencies"] = list(security_dependencies)
        app.include_router(**include_kwargs)


def register_metrics_endpoint(app: FastAPI) -> None:
    """Expose the Prometheus metrics endpoint if available."""

    if generate_latest is None:
        return
    metrics_generator = generate_latest

    @app.get("/metrics", tags=["telemetry"])
    def metrics_endpoint() -> PlainTextResponse:
        payload = metrics_generator()
        return PlainTextResponse(payload, media_type=CONTENT_TYPE_LATEST)


def mount_mcp(app: FastAPI, *, enabled: bool) -> None:
    """Mount the MCP server when requested."""

    if not enabled:
        return
    try:
        from mcp_server.server import app as mcp_app
    except ImportError as exc:  # pragma: no cover - defensive guard
        logger.warning(
            "MCP tools enabled but server package import failed: %s", exc
        )
        return
    app.mount("/mcp", mcp_app)
    logger.info("Mounted MCP server at /mcp")


def get_router_registrations() -> tuple[RouterRegistration, ...]:
    """Return the materialized router registrations."""

    return tuple(iter_router_registrations())


ROUTER_REGISTRATIONS = get_router_registrations()
