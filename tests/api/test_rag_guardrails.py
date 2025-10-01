import json
from pathlib import Path

import pytest

from theo.services.api.app.ai.rag.guardrails import guardrail_metadata
from theo.services.api.app.ai.rag.models import RAGAnswer, RAGCitation


@pytest.fixture
def golden_dir() -> Path:
    return Path(__file__).parent.parent / "golden" / "rag"


def test_guardrail_metadata_matches_golden(golden_dir: Path) -> None:
    citations = [
        RAGCitation(
            index=1,
            osis="John.1.1",
            anchor="John 1:1",
            passage_id="passage-1",
            document_id="doc-1",
            document_title="Gospel of John",
            snippet="In the beginning was the Word, and the Word was with God, and the Word was God.",
            source_url="/doc/doc-1#passage-1",
        ),
        RAGCitation(
            index=2,
            osis="Romans.5.5",
            anchor="Romans 5:5",
            passage_id="passage-2",
            document_id="doc-2",
            document_title="Letter to the Romans",
            snippet="Hope does not put us to shame, because God's love has been poured into our hearts.",
            source_url="/doc/doc-2#passage-2",
        ),
    ]
    answer = RAGAnswer(
        summary="Hope anchors believers in Christ's presence and assures them of God's love.",
        citations=citations,
        model_name="theo-gpt",
        model_output=(
            "Christian hope trusts God's promises revealed in Christ, remaining steadfast because "
            "God's love is poured into believers through the Spirit.\n\nSources: [1] John.1.1 (John 1:1); "
            "[2] Romans.5.5 (Romans 5:5)"
        ),
    )

    metadata = guardrail_metadata(answer)

    golden_path = golden_dir / "guardrail_metadata_basic.json"
    assert golden_path.exists(), "Golden guardrail metadata file is missing"
    assert metadata == json.loads(golden_path.read_text())
