from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import sys
import types

if "cachetools" not in sys.modules:
    cachetools_stub = types.ModuleType("cachetools")

    class _DummyLRUCache(dict):
        def __init__(self, *args, **kwargs) -> None:  # noqa: D401 - simple stub
            super().__init__()

        def __call__(self, *args, **kwargs):  # pragma: no cover - unused but defensive
            return self

    cachetools_stub.LRUCache = _DummyLRUCache  # type: ignore[attr-defined]
    sys.modules["cachetools"] = cachetools_stub

import pytest

from theo.infrastructure.api.app.routes.ai.workflows import chat


@dataclass
class _MemoryEntry:
    question: str
    answer: str
    answer_summary: str | None
    embedding: list[float] | None
    embedding_model: str | None
    created_at: datetime


class _StubMemoryIndex:
    def __init__(self, query_embedding: list[float] | None) -> None:
        self._query_embedding = query_embedding
        self.model_name = "stub-index"

    def embed_query(self, prompt: str) -> list[float] | None:  # noqa: ARG002 - parity with real API
        return self._query_embedding

    def score_similarity(
        self,
        query_embedding: list[float],
        snippet_embedding: list[float],
    ) -> float | None:
        if len(query_embedding) != len(snippet_embedding):
            return None
        return float(
            sum(component * other for component, other in zip(query_embedding, snippet_embedding))
        )


def _build_entry(
    *,
    created_at: datetime,
    question: str,
    answer: str,
    embedding: list[float] | None,
) -> _MemoryEntry:
    return _MemoryEntry(
        question=question,
        answer=answer,
        answer_summary=None,
        embedding=embedding,
        embedding_model="stub-index" if embedding else None,
        created_at=created_at,
    )


def test_prepare_memory_context_prioritises_similarity(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(UTC)
    entries = [
        _build_entry(
            created_at=now - timedelta(days=2),
            question="Earlier but relevant?",
            answer="An older yet highly relevant answer.",
            embedding=[1.0, 0.0, 0.0],
        ),
        _build_entry(
            created_at=now - timedelta(days=1),
            question="Another detail?",
            answer="A tangential response.",
            embedding=[0.1, 0.9, 0.0],
        ),
        _build_entry(
            created_at=now,
            question="Most recent but neutral?",
            answer="Latest comment.",
            embedding=[0.0, 0.0, 1.0],
        ),
    ]

    stub_index = _StubMemoryIndex([1.0, 0.0, 0.0])
    monkeypatch.setattr(chat.memory_index_module, "get_memory_index", lambda: stub_index)

    context = chat._prepare_memory_context(entries, query="Tell me about the earlier topic")

    assert len(context) >= 2
    assert context[0].startswith("Q: Earlier but relevant?")
    # Remaining slots should be filled by recency, skipping already-selected entries.
    assert any(snippet.startswith("Q: Most recent but neutral?") for snippet in context[1:])


def test_prepare_memory_context_handles_missing_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(UTC)
    entries = [
        _build_entry(
            created_at=now - timedelta(days=2),
            question="First question?",
            answer="First answer.",
            embedding=None,
        ),
        _build_entry(
            created_at=now - timedelta(days=1),
            question="Second question?",
            answer="Second answer.",
            embedding=None,
        ),
        _build_entry(
            created_at=now,
            question="Latest question?",
            answer="Latest answer.",
            embedding=None,
        ),
    ]

    stub_index = _StubMemoryIndex([0.0, 1.0, 0.0])
    monkeypatch.setattr(chat.memory_index_module, "get_memory_index", lambda: stub_index)

    context = chat._prepare_memory_context(entries, query="Anything at all")

    assert len(context) == 3
    # Without embeddings we fall back to the newest snippets first.
    assert context[0].startswith("Q: Latest question?")
    assert context[-1].startswith("Q: First question?")


def test_prepare_memory_context_respects_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(UTC)
    entry = _build_entry(
        created_at=now - timedelta(days=1),
        question="Budget heavy?",
        answer="This is a very long answer that should be trimmed to fit the tiny budget.",
        embedding=[1.0, 0.0, 0.0],
    )
    filler = _build_entry(
        created_at=now,
        question="Short?",
        answer="Short answer.",
        embedding=[0.0, 1.0, 0.0],
    )

    stub_index = _StubMemoryIndex([1.0, 0.0, 0.0])
    monkeypatch.setattr(chat.memory_index_module, "get_memory_index", lambda: stub_index)
    monkeypatch.setattr(chat, "CHAT_SESSION_MEMORY_CHAR_BUDGET", 32)

    context = chat._prepare_memory_context([entry, filler], query="Focus on the budget heavy")

    assert len(context) == 1
    assert context[0].startswith("Q: Budget heavy?")
    assert len(context[0]) <= 32
