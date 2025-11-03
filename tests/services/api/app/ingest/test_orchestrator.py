from __future__ import annotations

from dataclasses import dataclass

import pytest

from theo.infrastructure.api.app.ingest.orchestrator import IngestOrchestrator, OrchestratorResult, StageExecution
from theo.infrastructure.api.app.ingest.stages import (
    DefaultErrorPolicy,
    ErrorDecision,
    ErrorPolicy,
    IngestContext,
    Instrumentation,
)


class _FakeEmbeddingService:
    def embed(self, texts):  # pragma: no cover - embedding not exercised
        return texts


@dataclass
class _ScriptedPolicy(ErrorPolicy):
    decisions: list[ErrorDecision]

    def decide(self, *, stage, error, attempt, context):
        if not self.decisions:
            return ErrorDecision(retry=False, max_retries=0)
        return self.decisions.pop(0)


class _SuccessfulFetcher:
    name = "fetcher"

    def fetch(self, *, context, state):
        state = dict(state)
        state["fetched"] = True
        return state


class _SuccessfulParser:
    name = "parser"

    def parse(self, *, context, state):
        assert state["fetched"] is True
        return {"parsed": True}


class _SuccessfulPersister:
    name = "persister"

    def persist(self, *, context, state):
        assert state["parsed"] is True
        return {"document": "ok"}


class _FailingFetcher:
    name = "failing_fetcher"

    def __init__(self, *, error: Exception) -> None:
        self._error = error

    def fetch(self, *, context, state):
        raise self._error


class _FallbackFetcher:
    name = "fallback_fetcher"

    def fetch(self, *, context, state):
        return {"document": "fallback"}


def _make_context(*, policy=None):
    return IngestContext(
        settings=object(),
        embedding_service=_FakeEmbeddingService(),
        instrumentation=Instrumentation(),
        error_policy=policy or DefaultErrorPolicy(),
    )


def test_orchestrator_runs_stages_successfully() -> None:
    orchestrator = IngestOrchestrator([_SuccessfulFetcher(), _SuccessfulParser(), _SuccessfulPersister()])
    context = _make_context()

    result = orchestrator.run(context=context)

    assert result.status == "success"
    assert result.state["document"] == "ok"
    assert len(result.stages) == 3
    assert all(stage.status == "success" for stage in result.stages)
    assert result.failures == []


def test_orchestrator_retries_with_fallback() -> None:
    error = RuntimeError("boom")
    fallback = _FallbackFetcher()
    policy = _ScriptedPolicy([
        ErrorDecision(retry=True, max_retries=1, fallback=fallback),
    ])
    orchestrator = IngestOrchestrator([_FailingFetcher(error=error)])
    context = _make_context(policy=policy)

    result = orchestrator.run(context=context)

    assert result.status == "success"
    assert result.state["document"] == "fallback"
    assert len(result.stages) == 1
    execution = result.stages[0]
    assert execution.name == fallback.name
    assert execution.attempts == 2
    assert result.failures == []


def test_orchestrator_records_failure_when_policy_stops_retry() -> None:
    error = ValueError("fatal")
    orchestrator = IngestOrchestrator([_FailingFetcher(error=error)])
    context = _make_context()

    result = orchestrator.run(context=context)

    assert result.status == "failed"
    assert result.state == {}
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert isinstance(failure, StageExecution)
    assert failure.error is error
    assert failure.attempts == 1

