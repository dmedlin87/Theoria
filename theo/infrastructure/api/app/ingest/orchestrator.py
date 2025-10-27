"""Composable ingestion orchestrator built from discrete stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, List

from .stages import Enricher, IngestContext, Parser, Persister, SourceFetcher


@dataclass(slots=True)
class StageExecution:
    """Structured record of a single stage execution."""

    name: str
    status: str
    attempts: int
    data: dict[str, Any] | None = None
    error: Exception | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OrchestratorResult:
    """Aggregate result for a full ingestion run."""

    status: str
    state: dict[str, Any]
    stages: list[StageExecution]
    failures: list[StageExecution]

    @property
    def document(self) -> Any | None:
        return self.state.get("document")

    @property
    def document_metadata(self) -> dict[str, Any]:
        return self.state.get("document_metadata", {})


class IngestOrchestrator:
    """Execute ingestion stages with retry-aware error handling."""

    def __init__(self, stages: Iterable[Any]):
        self._stages: List[Any] = list(stages)

    def run(self, *, context: IngestContext, initial_state: dict[str, Any] | None = None) -> OrchestratorResult:
        state: dict[str, Any] = initial_state.copy() if initial_state else {}
        stages: list[StageExecution] = []
        failures: list[StageExecution] = []

        for stage in self._stages:
            stage_name = getattr(stage, "name", stage.__class__.__name__)
            attempts = 0
            stage_state: dict[str, Any] | None = None
            error: Exception | None = None
            metadata: dict[str, Any] = {}
            current_stage = stage

            while True:
                attempts += 1
                try:
                    if isinstance(current_stage, SourceFetcher):
                        stage_state = current_stage.fetch(context=context, state=state)
                    elif isinstance(current_stage, Parser):
                        stage_state = current_stage.parse(context=context, state=state)
                    elif isinstance(current_stage, Enricher):
                        stage_state = current_stage.enrich(context=context, state=state)
                    elif isinstance(current_stage, Persister):
                        stage_state = current_stage.persist(context=context, state=state)
                    else:
                        raise TypeError(f"Unsupported stage type: {current_stage!r}")
                except Exception as exc:  # pragma: no cover - decision making tested separately
                    error = exc
                    decision = context.error_policy.decide(
                        stage=stage_name,
                        error=exc,
                        attempt=attempts,
                        context=context,
                    )
                    metadata = decision.metadata
                    allowed_attempts = 1 + max(decision.max_retries, 0)
                    if decision.retry and attempts < allowed_attempts:
                        if decision.fallback is not None:
                            current_stage = decision.fallback
                            stage_name = getattr(
                                current_stage, "name", current_stage.__class__.__name__
                            )
                        continue
                    failure = StageExecution(
                        name=stage_name,
                        status="failed",
                        attempts=attempts,
                        data=None,
                        error=error,
                        metadata=metadata,
                    )
                    stages.append(failure)
                    failures.append(failure)
                    return OrchestratorResult(
                        status="failed",
                        state=state,
                        stages=stages,
                        failures=failures,
                    )
                else:
                    state.update(stage_state or {})
                    execution = StageExecution(
                        name=stage_name,
                        status="success",
                        attempts=attempts,
                        data=stage_state,
                        metadata=metadata,
                    )
                    stages.append(execution)
                    break

        return OrchestratorResult(
            status="success",
            state=state,
            stages=stages,
            failures=failures,
        )
