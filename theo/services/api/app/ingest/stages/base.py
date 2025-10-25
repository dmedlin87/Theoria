"""Stage interfaces and shared orchestration state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Protocol, Sequence, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from theo.application.graph import GraphProjector


class EmbeddingServiceProtocol(Protocol):
    """Protocol for embedding providers used by ingestion stages."""

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        ...


@dataclass(slots=True)
class Instrumentation:
    """Container for instrumentation helpers shared across stages."""

    span: Any | None = None
    setter: Callable[[Any, str, Any], None] | None = None

    def set(self, key: str, value: Any) -> None:
        """Set an attribute on the active span if available."""

        if self.span is None:
            return
        setter = self.setter
        if setter is None:
            try:
                from theo.application.facades.telemetry import set_span_attribute as default_setter
            except Exception:  # pragma: no cover - defensive import
                return
            setter = default_setter
            self.setter = setter
        setter(self.span, key, value)


@dataclass(slots=True)
class ErrorDecision:
    """Decision returned by an error policy when handling a stage failure."""

    retry: bool = False
    max_retries: int = 0
    fallback: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ErrorPolicy(Protocol):
    """Protocol for pluggable error handling strategies."""

    def decide(
        self,
        *,
        stage: str,
        error: Exception,
        attempt: int,
        context: "IngestContext",
    ) -> ErrorDecision:
        ...


@dataclass(slots=True)
class DefaultErrorPolicy:
    """Error policy that records failures without retries."""

    def decide(
        self,
        *,
        stage: str,
        error: Exception,
        attempt: int,
        context: "IngestContext",
    ) -> ErrorDecision:
        return ErrorDecision(retry=False, max_retries=0)


@dataclass(slots=True)
class IngestContext:
    """Shared runtime state for a single ingestion request."""

    settings: Any
    embedding_service: EmbeddingServiceProtocol
    instrumentation: Instrumentation
    error_policy: ErrorPolicy = field(default_factory=DefaultErrorPolicy)
    graph_projector: "GraphProjector | None" = None


@runtime_checkable
class Stage(Protocol):
    """Base protocol for ingestion stages."""

    name: str


@runtime_checkable
class SourceFetcher(Stage, Protocol):
    """Fetch an input document from a backing source."""

    def fetch(self, *, context: IngestContext, state: dict[str, Any]) -> dict[str, Any]:
        ...


@runtime_checkable
class Parser(Stage, Protocol):
    """Parse fetched content into chunked representations."""

    def parse(self, *, context: IngestContext, state: dict[str, Any]) -> dict[str, Any]:
        ...


@runtime_checkable
class Enricher(Stage, Protocol):
    """Derive metadata after parsing but before persistence."""

    def enrich(self, *, context: IngestContext, state: dict[str, Any]) -> dict[str, Any]:
        ...


@runtime_checkable
class Persister(Stage, Protocol):
    """Persist parsed and enriched content to durable storage."""

    def persist(
        self,
        *,
        context: IngestContext,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        ...
