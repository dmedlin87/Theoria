"""Runtime health probing utilities for core infrastructure adapters."""

from __future__ import annotations

import contextlib
import math
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Callable, Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

from theo.application.facades.database import get_engine, get_session
from theo.application.facades.settings import get_settings

from ..db.verse_graph import load_seed_relationships
from ..ingest.embeddings import get_embedding_service

try:  # pragma: no cover - redis is an optional dependency at runtime
    import redis
except ImportError:  # pragma: no cover - exercised when redis isn't installed
    redis = None  # type: ignore[assignment]


class HealthStatus(str, Enum):
    """Normalised health states for infrastructure adapters."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"

    @property
    def severity(self) -> int:
        """Return a numeric representation used for comparisons."""

        return {
            HealthStatus.HEALTHY: 0,
            HealthStatus.DEGRADED: 1,
            HealthStatus.UNAVAILABLE: 2,
        }[self]


class HealthProbeError(RuntimeError):
    """Raised when a probe is unable to verify an adapter's availability."""

    def __init__(self, message: str, *, status: HealthStatus) -> None:
        super().__init__(message)
        self.status = status


ProbeCallable = Callable[[], str | None]


@dataclass(slots=True)
class AdapterHealth:
    """Observed health metadata for a single adapter."""

    name: str
    status: HealthStatus
    latency_ms: float | None
    message: str | None

    def to_summary_dict(self) -> dict[str, str | float | None]:
        """Serialise the adapter into a lightweight API representation."""

        return {
            "name": self.name,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "message": self.message,
        }


@dataclass(slots=True)
class HealthReport:
    """Aggregated health snapshot for all configured adapters."""

    status: HealthStatus
    checked_at: datetime
    adapters: dict[str, AdapterHealth]

    def _compose_message(self) -> str:
        if self.status is HealthStatus.HEALTHY:
            return "All systems operational."
        issues: list[str] = []
        for adapter in self.adapters.values():
            if adapter.status is HealthStatus.HEALTHY:
                continue
            detail = adapter.message or adapter.status.value.capitalize()
            issues.append(f"{adapter.name}: {detail}")
        if not issues:
            return "Service health degraded."
        return "; ".join(issues)

    def to_summary(self) -> dict[str, object]:
        """Return a condensed representation for lightweight polls."""

        return {
            "status": self.status.value,
            "message": self._compose_message(),
            "checked_at": self.checked_at.isoformat(),
            "adapters": {
                name: adapter.status.value for name, adapter in self.adapters.items()
            },
        }

    def to_detail(self) -> dict[str, object]:
        """Return an expanded representation with adapter metadata."""

        return {
            "status": self.status.value,
            "message": self._compose_message(),
            "checked_at": self.checked_at.isoformat(),
            "adapters": [
                adapter.to_summary_dict() for adapter in self.adapters.values()
            ],
        }


class HealthService:
    """Coordinator responsible for executing adapter health probes."""

    def __init__(self, probes: dict[str, ProbeCallable]) -> None:
        self._probes = dict(probes)

    def _run_probe(self, name: str, probe: ProbeCallable) -> AdapterHealth:
        start = time.perf_counter()
        message: str | None = None
        status = HealthStatus.HEALTHY
        try:
            result = probe()
            if result:
                message = result
        except HealthProbeError as exc:
            status = exc.status
            message = str(exc) or None
        except Exception as exc:  # pragma: no cover - defensive safety net
            status = HealthStatus.UNAVAILABLE
            message = f"{exc.__class__.__name__}: {exc}"
        elapsed_ms = (time.perf_counter() - start) * 1000
        latency = round(elapsed_ms, 2)
        if math.isnan(latency) or math.isinf(latency):
            latency = None
        return AdapterHealth(
            name=name,
            status=status,
            latency_ms=latency,
            message=message,
        )

    def check(self) -> HealthReport:
        """Execute configured probes and collate the results."""

        adapters: dict[str, AdapterHealth] = {}
        overall = HealthStatus.HEALTHY
        for name, probe in self._probes.items():
            adapter = self._run_probe(name, probe)
            adapters[name] = adapter
            if adapter.status.severity > overall.severity:
                overall = adapter.status
        return HealthReport(
            status=overall,
            checked_at=datetime.now(UTC),
            adapters=adapters,
        )


def _with_session() -> Iterable[Session]:
    session_context = get_session()
    session = next(session_context)
    try:
        yield session
    finally:
        with contextlib.suppress(StopIteration):
            next(session_context)


def probe_database() -> str | None:
    """Verify the primary relational database connection."""

    engine = get_engine()
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))  # nosec B608 - healthcheck probe
    return "Database reachable"


def probe_redis() -> str | None:
    """Verify Redis connectivity for background workers and caching."""

    settings = get_settings()
    if not settings.redis_url:
        raise HealthProbeError("Redis URL not configured", status=HealthStatus.DEGRADED)
    if redis is None:
        raise HealthProbeError("redis client library is not installed", status=HealthStatus.DEGRADED)
    client = redis.Redis.from_url(  # type: ignore[assignment]
        settings.redis_url,
        socket_connect_timeout=1.5,
        socket_timeout=1.5,
        retry_on_timeout=False,
    )
    try:
        if not bool(client.ping()):
            raise HealthProbeError("Redis ping unsuccessful", status=HealthStatus.UNAVAILABLE)
    except redis.exceptions.ConnectionError as exc:  # type: ignore[attr-defined]
        raise HealthProbeError(str(exc), status=HealthStatus.UNAVAILABLE) from exc
    finally:
        with contextlib.suppress(Exception):
            client.close()
    return "Redis reachable"


def probe_embeddings() -> str | None:
    """Verify embedding service availability."""

    service = get_embedding_service()
    vectors = service.embed(["theoria-healthcheck"], batch_size=1)
    if not vectors or not vectors[0]:
        raise HealthProbeError("Embedding vector not generated", status=HealthStatus.DEGRADED)
    return f"Embedding service ready (dim={len(vectors[0])})"


def probe_verse_graph() -> str | None:
    """Verify the ability to read verse relationship seed data."""

    for session in _with_session():
        load_seed_relationships(session, "John.3.16")
    return "Verse graph queryable"


DEFAULT_PROBES: dict[str, ProbeCallable] = {
    "database": probe_database,
    "redis": probe_redis,
    "embeddings": probe_embeddings,
    "graph": probe_verse_graph,
}


def get_health_service() -> HealthService:
    """Return a health service initialised with default adapter probes."""

    return HealthService(dict(DEFAULT_PROBES))

