"""Helpers for embedding and ranking conversational memories."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol, Sequence, runtime_checkable

from ..ingest.embeddings import get_embedding_service
from ..ingest.stages.base import EmbeddingServiceProtocol

if TYPE_CHECKING:
    from ..models.ai import ChatMemoryEntry


@runtime_checkable
class _ModelNamed(Protocol):
    model_name: str | None


LOGGER = logging.getLogger(__name__)


def render_memory_snippet(
    question: str,
    answer: str,
    *,
    answer_summary: str | None = None,
) -> str:
    """Return the canonical text representation for a memory snippet."""

    question_text = (question or "").strip()
    answer_text = (answer_summary or answer or "").strip()

    if question_text and answer_text:
        return f"Q: {question_text} | A: {answer_text}"
    if question_text:
        return f"Q: {question_text}"
    return answer_text


def snippet_from_entry(entry: "ChatMemoryEntry") -> str:
    """Render a snippet string for ``entry`` using the canonical format."""

    return render_memory_snippet(
        entry.question,
        entry.answer,
        answer_summary=entry.answer_summary,
    )


class MemoryIndex:
    """Embedding-backed similarity helper for chat memories."""

    def __init__(
        self,
        *,
        embedding_service: EmbeddingServiceProtocol | None = None,
    ) -> None:
        self._embedding_service = embedding_service

    @property
    def model_name(self) -> str | None:
        service = self._embedding_service
        if isinstance(service, _ModelNamed):
            return service.model_name
        if service is None:
            try:
                service = self._ensure_service()
            except Exception:  # pragma: no cover - defensive guard
                return None
        if isinstance(service, _ModelNamed):
            return service.model_name
        return None

    def embed_snippet(
        self,
        *,
        question: str,
        answer: str,
        answer_summary: str | None = None,
    ) -> list[float] | None:
        """Embed a Q/A snippet and return the resulting vector."""

        text = render_memory_snippet(question, answer, answer_summary=answer_summary)
        return self._embed_text(text)

    def embed_entry(self, entry: "ChatMemoryEntry") -> list[float] | None:
        """Embed an existing memory entry."""

        return self._embed_text(snippet_from_entry(entry))

    def embed_query(self, prompt: str) -> list[float] | None:
        """Embed the current user prompt for similarity search."""

        return self._embed_text(prompt)

    def score_similarity(
        self,
        query_embedding: Sequence[float],
        snippet_embedding: Sequence[float],
    ) -> float | None:
        """Return the cosine similarity between the query and snippet."""

        if not query_embedding or not snippet_embedding:
            return None
        if len(query_embedding) != len(snippet_embedding):
            return None
        return float(
            sum(component * other for component, other in zip(query_embedding, snippet_embedding))
        )

    def _embed_text(self, text: str) -> list[float] | None:
        text = (text or "").strip()
        if not text:
            return None
        try:
            service = self._ensure_service()
            vectors = service.embed([text])
        except Exception:  # pragma: no cover - embedding failures should be non-fatal
            LOGGER.warning("Failed to embed chat memory snippet", exc_info=True)
            return None
        if not vectors:
            return None
        vector = vectors[0]
        return [float(component) for component in vector]

    def _ensure_service(self) -> EmbeddingServiceProtocol:
        if self._embedding_service is None:
            self._embedding_service = get_embedding_service()
        return self._embedding_service


_MEMORY_INDEX: MemoryIndex | None = None


def get_memory_index() -> MemoryIndex:
    """Return a process-wide ``MemoryIndex`` instance."""

    global _MEMORY_INDEX
    if _MEMORY_INDEX is None:
        _MEMORY_INDEX = MemoryIndex()
    return _MEMORY_INDEX


__all__ = [
    "MemoryIndex",
    "get_memory_index",
    "render_memory_snippet",
    "snippet_from_entry",
]
