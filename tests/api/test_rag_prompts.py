from pathlib import Path

import pytest

from theo.infrastructure.api.app.ai.rag.prompts import PromptContext


@pytest.fixture
def golden_dir() -> Path:
    return Path(__file__).parent.parent / "golden" / "rag"


def test_prompt_context_build_prompt_matches_golden(
    golden_dir: Path, regression_factory
) -> None:
    citations = regression_factory.rag_citations(2)
    context = PromptContext(
        citations=citations,
        memory_context=regression_factory.conversation_highlights(),
    )

    prompt = context.build_prompt(regression_factory.question())

    golden_path = golden_dir / "prompt_context_basic.txt"
    assert golden_path.exists(), "Golden prompt file is missing"
    golden_text = golden_path.read_text(encoding="utf-8").rstrip("\n")
    assert prompt == golden_text


def test_prompt_context_build_summary_matches_golden(
    golden_dir: Path, regression_factory
) -> None:
    citations = regression_factory.rag_citations(2)
    context = PromptContext(citations=citations)

    summary, lines = context.build_summary([])

    golden_path = golden_dir / "prompt_summary_basic.txt"
    assert golden_path.exists(), "Golden prompt summary file is missing"
    assert summary == golden_path.read_text(encoding="utf-8").rstrip("\n")
    assert lines == summary.splitlines()
