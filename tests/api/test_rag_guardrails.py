import json
from pathlib import Path

import pytest

from theo.infrastructure.api.app.ai.rag.guardrails import guardrail_metadata


@pytest.fixture
def golden_dir() -> Path:
    return Path(__file__).parent.parent / "golden" / "rag"


def test_guardrail_metadata_matches_golden(
    golden_dir: Path, regression_factory
) -> None:
    citations = regression_factory.rag_citations(2)
    answer = regression_factory.rag_answer(citations=citations)

    metadata = guardrail_metadata(answer)

    golden_path = golden_dir / "guardrail_metadata_basic.json"
    assert golden_path.exists(), "Golden guardrail metadata file is missing"
    assert metadata == json.loads(golden_path.read_text())
