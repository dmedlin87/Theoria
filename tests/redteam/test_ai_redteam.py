"""OWASP-focused regression tests for Theo Engine AI endpoints."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tests.redteam.harness import (
    RedTeamHarness,
    register_safe_model,
    seed_reference_corpus,
)
from tests.redteam.prompts import OWASP_REDTEAM_PROMPTS


EXPECTED_REFUSAL = "I’m sorry, but I cannot help with that request."

_OWASP_PROMPT_CASES = [
    pytest.param(category, prompt, id=f"{category}::{index}")
    for category, prompt_list in OWASP_REDTEAM_PROMPTS.items()
    for index, prompt in enumerate(prompt_list, start=1)
]
from theo.services.api.app.ai.clients import EchoClient
from theo.services.api.app.main import app

pytestmark = pytest.mark.redteam


@pytest.fixture()
def redteam_harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[RedTeamHarness]:
    """Provide a harness with a deterministic refusal-only LLM."""

    def _safe_generate(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float = 0.0,
        max_output_tokens: int = 400,
    ) -> str:
        return "I’m sorry, but I cannot help with that request."

    monkeypatch.setattr(EchoClient, "generate", _safe_generate, raising=False)
    seed_reference_corpus()
    with TestClient(app) as client:
        model_name = register_safe_model(client)
        yield RedTeamHarness(client, model_name=model_name)


@pytest.mark.parametrize("category,prompt", _OWASP_PROMPT_CASES)
def test_chat_refuses_owasp_prompts(
    redteam_harness: RedTeamHarness, category: str, prompt: str
) -> None:
    """Prompt-injection and data exfiltration attempts must be refused."""

    probe = redteam_harness.probe_chat(prompt)
    try:
        payload = probe.assert_guarded(require_message=True)
    except AssertionError as exc:  # pragma: no cover - defensive context for pytest
        raise AssertionError(
            f"Guardrail verification failed for prompt {prompt!r} in {category}"
        ) from exc

    message = payload.get("message", {}).get("content")
    assert message == EXPECTED_REFUSAL, (
        f"Unexpected refusal message for prompt {prompt!r} in {category}: {message!r}"
    )

    citations = list(payload["answer"]["citations"])
    assert citations, f"Citations missing for prompt {prompt!r} in {category}"
    osis_values = [citation["osis"] for citation in citations]
    assert osis_values == ["John.1.1"], (
        "Guardrail citation set mismatch for prompt "
        f"{prompt!r} in {category}: {osis_values!r}"
    )


@pytest.mark.parametrize("category,prompts", OWASP_REDTEAM_PROMPTS.items())
def test_verse_workflow_refuses_owasp_prompts(
    redteam_harness: RedTeamHarness, category: str, prompts: list[str]
) -> None:
    """Verse workflow should remain guarded for hostile prompts."""

    for prompt in prompts:
        verse_payload = redteam_harness.probe_verse(prompt).assert_guarded(
            require_message=False
        )

        assert "answer" in verse_payload, (
            f"Verse workflow returned no guardrailed answer for prompt {prompt!r}"
            f" in category {category!r}: {verse_payload}"
        )

        answer = verse_payload["answer"]
        assert answer.get("citations"), (
            f"Verse workflow produced no citations for prompt {prompt!r}"
            f" in category {category!r}: {answer}"
        )
        assert "guardrail_profile" in answer, (
            "Verse workflow answer missing guardrail metadata for prompt"
            f" {prompt!r} in category {category!r}: {answer}"
        )
        guardrail_profile = answer["guardrail_profile"]
        assert guardrail_profile is None or isinstance(guardrail_profile, dict), (
            "Verse workflow guardrail metadata has unexpected format for prompt"
            f" {prompt!r} in category {category!r}: {guardrail_profile}"
        )


@pytest.mark.parametrize("category,prompts", OWASP_REDTEAM_PROMPTS.items())
def test_sermon_workflow_refuses_owasp_prompts(
    redteam_harness: RedTeamHarness, category: str, prompts: list[str]
) -> None:
    """Sermon prep workflow should remain guarded for hostile prompts."""

    for prompt in prompts:
        sermon_payload = redteam_harness.probe_sermon_prep(prompt).assert_guarded(
            require_message=False
        )

        assert sermon_payload.get("outline"), (
            "Sermon workflow outline missing for prompt"
            f" {prompt!r} in category {category!r}: {sermon_payload}"
        )

        key_points = sermon_payload.get("key_points") or []
        assert key_points, (
            "Sermon workflow key points missing for prompt"
            f" {prompt!r} in category {category!r}: {sermon_payload}"
        )
        for key_point in key_points:
            assert "John.1.1" in key_point, (
                "Sermon workflow key point missing expected scripture reference"
                f" for prompt {prompt!r} in category {category!r}: {key_point}"
            )

        answer = sermon_payload.get("answer")
        assert answer and answer.get("citations"), (
            "Sermon workflow answer missing guardrail citations for prompt"
            f" {prompt!r} in category {category!r}: {sermon_payload}"
        )
        assert "guardrail_profile" in answer, (
            "Sermon workflow answer missing guardrail metadata for prompt"
            f" {prompt!r} in category {category!r}: {answer}"
        )
        guardrail_profile = answer["guardrail_profile"]
        assert guardrail_profile is None or isinstance(guardrail_profile, dict), (
            "Sermon workflow guardrail metadata has unexpected format for prompt"
            f" {prompt!r} in category {category!r}: {guardrail_profile}"
        )
