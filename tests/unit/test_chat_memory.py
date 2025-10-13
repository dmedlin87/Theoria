from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from theo.services.api.app.ai.memory_metadata import extract_memory_metadata
from theo.services.api.app.ai.rag.models import RAGAnswer, RAGCitation
from theo.services.api.app.models.ai import ChatMemoryEntry, IntentTagPayload
from theo.services.api.app.routes.ai.workflows.chat import (
    _load_memory_entries,
    _prepare_memory_context,
)


def test_extract_memory_metadata_infers_fields() -> None:
    answer = RAGAnswer(
        summary="Paul encourages the weary church with hope and love.",
        citations=[
            RAGCitation(
                index=0,
                osis="1Cor.13.1",
                anchor="Love is patient",
                passage_id="pass-1",
                document_id="doc-1",
                document_title="Commentary on Corinthians",
                snippet="Love bears all things.",
                source_url="https://example.com/commentary",
            )
        ],
    )
    intent_tags = [
        IntentTagPayload(intent="pastoral_care", stance="supportive", confidence=0.9)
    ]

    metadata = extract_memory_metadata(
        question="How can we encourage exhausted believers?",
        answer=answer,
        intent_tags=intent_tags,
    )

    assert metadata.goal_ids == ["pastoral_care"]
    assert metadata.sentiment == "positive"
    assert metadata.entities == ["1Cor.13.1", "Commentary on Corinthians"]
    assert metadata.source_types == ["scripture", "example.com", "document"]
    assert metadata.topics and "hope" in metadata.topics


def test_prepare_memory_context_prioritises_focus_matches() -> None:
    now = datetime.now(UTC)
    matching_entry = ChatMemoryEntry(
        question="How do we encourage hope?",
        answer="Extend love toward weary hearts.",
        created_at=now - timedelta(minutes=10),
        intent_tags=None,
        prompt=None,
        answer_summary=None,
        topics=["hope", "love"],
        goal_ids=["pastoral_care"],
    )
    recent_entry = ChatMemoryEntry(
        question="Explain covenant law.",
        answer="Discuss the Mosaic covenant provisions.",
        created_at=now - timedelta(minutes=2),
        intent_tags=None,
        prompt=None,
        answer_summary=None,
        topics=["law"],
    )

    focus_metadata = extract_memory_metadata(
        question="I need pastoral care ideas for hope.",
        answer=None,
        intent_tags=[IntentTagPayload(intent="pastoral_care")],
    )
    focus = focus_metadata.to_focus()
    context = _prepare_memory_context([matching_entry, recent_entry], focus=focus)

    assert context
    assert "encourage hope" in context[0].lower()


def test_load_memory_entries_handles_legacy_payloads() -> None:
    created_at = datetime.now(UTC).isoformat()
    legacy_entry = {
        "question": "What is faith?",
        "answer": "Faith is confidence in things hoped for.",
        "created_at": created_at,
    }
    record = SimpleNamespace(id="legacy", memory_snippets=[legacy_entry])

    entries = _load_memory_entries(record)
    assert entries and entries[0].topics is None

    context = _prepare_memory_context(entries, focus=None)
    assert context and "what is faith" in context[0].lower()
