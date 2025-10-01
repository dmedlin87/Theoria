from pathlib import Path

import pytest

from theo.services.api.app.ai.rag.models import RAGCitation
from theo.services.api.app.ai.rag.prompts import PromptContext


@pytest.fixture
def golden_dir() -> Path:
    return Path(__file__).parent.parent / "golden" / "rag"


def test_prompt_context_build_prompt_matches_golden(golden_dir: Path) -> None:
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
    context = PromptContext(
        citations=citations,
        memory_context=[
            "Earlier you reflected on perseverance and faith.",
            "User asked about how hope relates to suffering.",
        ],
    )

    prompt = context.build_prompt("What is Christian hope?")

    golden_path = golden_dir / "prompt_context_basic.txt"
    assert golden_path.exists(), "Golden prompt file is missing"
    assert prompt == golden_path.read_text().rstrip("\n")


def test_prompt_context_build_summary_matches_golden(golden_dir: Path) -> None:
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
    context = PromptContext(citations=citations)

    summary, lines = context.build_summary([])

    golden_path = golden_dir / "prompt_summary_basic.txt"
    assert golden_path.exists(), "Golden prompt summary file is missing"
    assert summary == golden_path.read_text().rstrip("\n")
    assert lines == summary.splitlines()
