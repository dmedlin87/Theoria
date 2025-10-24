"""Unit tests for the guardrailed reasoning helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from theo.services.api.app.ai.rag import reasoning


class RecorderStub:
    """Captures log_step payloads for assertions."""

    def __init__(self) -> None:
        self.steps: list[dict[str, object]] = []

    def log_step(self, **payload: object) -> None:
        self.steps.append(payload)


class DummyModel:
    """LLM model stub that records build_client usage."""

    model = "demo-model"

    def __init__(self) -> None:
        self.builds: int = 0

    def build_client(self) -> object:
        self.builds += 1
        return object()


@pytest.fixture()
def base_monkeypatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset dynamic dependencies in the reasoning module to controllable stubs."""

    chain = SimpleNamespace(raw_thinking="deliberation")
    monkeypatch.setattr(reasoning, "parse_chain_of_thought", lambda answer: chain)

    critique = SimpleNamespace(reasoning_quality=70)
    monkeypatch.setattr(reasoning, "critique_reasoning", lambda **_: critique)

    monkeypatch.setattr(reasoning, "critique_to_schema", lambda crit: SimpleNamespace(reasoning_quality=crit.reasoning_quality))
    monkeypatch.setattr(
        reasoning,
        "build_reasoning_trace_from_completion",
        lambda answer, mode=None: SimpleNamespace(rendered=answer, mode=mode),
    )


def test_run_reasoning_review_records_revision_event(base_monkeypatch: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """When a revision succeeds the telemetry hook should be invoked and the answer updated."""

    recorder = RecorderStub()
    model = DummyModel()

    monkeypatch.setattr(reasoning, "should_attempt_revision", lambda critique: True)

    revision_result = SimpleNamespace(
        revised_answer="Improved answer",
        critique_addressed=["fallacy"],
        quality_delta=12,
        revised_critique=SimpleNamespace(reasoning_quality=88),
    )

    monkeypatch.setattr(reasoning, "revise_with_critique", lambda **kwargs: revision_result)
    monkeypatch.setattr(
        reasoning,
        "revision_to_schema",
        lambda result: SimpleNamespace(
            revised_answer=result.revised_answer,
            quality_delta=result.quality_delta,
            critique_addressed=result.critique_addressed,
        ),
    )

    recorded: dict[str, object] = {}

    def _record_revision_event(**payload: object) -> None:
        recorded.update(payload)

    monkeypatch.setattr(reasoning, "record_revision_event", _record_revision_event)

    outcome = reasoning.run_reasoning_review(
        answer="Initial answer",
        citations=[],
        selected_model=model,
        recorder=recorder,
        mode="chat",
    )

    assert outcome.answer == "Improved answer"
    assert outcome.revision.quality_delta == 12
    assert recorded == {"quality_delta": 12, "addressed": 1}
    assert model.builds == 1
    assert recorder.steps[-1]["tool"] == "rag.revise"
    assert recorder.steps[-1]["output_payload"]["quality_delta"] == 12


def test_run_reasoning_review_handles_revision_failure(base_monkeypatch: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """If revision generation fails the original answer should be preserved."""

    recorder = RecorderStub()
    model = DummyModel()

    monkeypatch.setattr(reasoning, "should_attempt_revision", lambda critique: True)

    def _raise_generation_error(**kwargs: object) -> None:
        raise reasoning.GenerationError("model error")

    monkeypatch.setattr(reasoning, "revise_with_critique", _raise_generation_error)
    monkeypatch.setattr(reasoning, "record_revision_event", lambda **_: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(reasoning, "revision_to_schema", lambda result: result)

    outcome = reasoning.run_reasoning_review(
        answer="Original answer",
        citations=[],
        selected_model=model,
        recorder=recorder,
    )

    assert outcome.answer == "Original answer"
    assert outcome.revision is None
    assert model.builds == 1
    assert recorder.steps[-1]["status"] == "failed"
