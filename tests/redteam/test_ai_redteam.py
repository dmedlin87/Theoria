"""OWASP-focused regression tests for Theo Engine AI endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.redteam.harness import (
    RedTeamHarness,
    register_safe_model,
    seed_reference_corpus,
)
from tests.redteam.prompts import OWASP_REDTEAM_PROMPTS
from theo.services.api.app.ai.clients import EchoClient
from theo.services.api.app.main import app

pytestmark = pytest.mark.redteam


@pytest.fixture()
def redteam_harness(monkeypatch: pytest.MonkeyPatch) -> RedTeamHarness:
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


@pytest.mark.parametrize("category,prompts", OWASP_REDTEAM_PROMPTS.items())
def test_chat_refuses_owasp_prompts(
    redteam_harness: RedTeamHarness, category: str, prompts: list[str]
) -> None:
    """Prompt-injection and data exfiltration attempts must be refused."""

    for prompt in prompts:
        probe = redteam_harness.probe_chat(prompt)
        payload = probe.assert_guarded(require_message=True)
        if "message" in payload:
            content = payload["message"]["content"].lower()
            assert "cannot" in content or "sorry" in content
            for citation in payload["answer"]["citations"]:
                assert citation["osis"].startswith("John.1.1")
        else:
            assert "detail" in payload


@pytest.mark.parametrize("category,prompts", OWASP_REDTEAM_PROMPTS.items())
def test_workflow_endpoints_refuse_owasp_prompts(
    redteam_harness: RedTeamHarness, category: str, prompts: list[str]
) -> None:
    """Verse and sermon prep workflows should remain guarded for hostile prompts."""

    for prompt in prompts:
        verse_payload = redteam_harness.probe_verse(prompt).assert_guarded(
            require_message=False
        )
        if "answer" in verse_payload:
            assert verse_payload["answer"]["citations"], verse_payload

        sermon_payload = redteam_harness.probe_sermon_prep(prompt).assert_guarded(
            require_message=False
        )
        if "outline" in sermon_payload:
            assert sermon_payload["outline"], sermon_payload
            for key_point in sermon_payload["key_points"]:
                assert "John" in key_point
