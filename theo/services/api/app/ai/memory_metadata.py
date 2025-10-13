"""Utilities for enriching and selecting chat memory metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence, TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:  # pragma: no cover - used only for type checking
    from ..models.ai import ChatMemoryEntry, IntentTagPayload
    from .rag import RAGAnswer, RAGCitation
else:  # pragma: no cover - help mypy without runtime imports
    ChatMemoryEntry = object  # type: ignore[assignment]
    IntentTagPayload = object  # type: ignore[assignment]
    RAGAnswer = object  # type: ignore[assignment]
    RAGCitation = object  # type: ignore[assignment]

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "there",
    "they",
    "to",
    "was",
    "were",
    "with",
    "you",
}

_POSITIVE_WORDS = {
    "assurance",
    "blessing",
    "comfort",
    "encourage",
    "encourages",
    "faith",
    "grace",
    "gratitude",
    "hope",
    "joy",
    "love",
    "mercy",
    "peace",
    "rejoice",
}

_NEGATIVE_WORDS = {
    "anger",
    "broken",
    "condemn",
    "fear",
    "grief",
    "judgment",
    "lament",
    "loss",
    "sin",
    "sorrow",
    "struggle",
    "suffering",
    "wrath",
}

_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9'_-]*")


@dataclass
class MemoryMetadata:
    """Structured metadata extracted for a chat memory turn."""

    topics: list[str] | None = None
    entities: list[str] | None = None
    goal_ids: list[str] | None = None
    source_types: list[str] | None = None
    sentiment: str | None = None

    def to_focus(self) -> "MemoryFocus | None":
        """Convert the metadata into a focus object for selection heuristics."""

        topics = {item.lower() for item in self.topics or [] if item}
        entities = {item.lower() for item in self.entities or [] if item}
        goal_ids = {item.lower() for item in self.goal_ids or [] if item}
        if not (topics or entities or goal_ids):
            return None
        return MemoryFocus(topics=topics, entities=entities, goal_ids=goal_ids)


@dataclass(frozen=True)
class MemoryFocus:
    """Search criteria used to prioritise relevant memory entries."""

    topics: set[str]
    entities: set[str]
    goal_ids: set[str]

    def matches(self, entry: "ChatMemoryEntry") -> bool:
        """Return ``True`` when a memory entry intersects the focus criteria."""

        entry_topics = {
            str(value).lower()
            for value in getattr(entry, "topics", None) or []
            if value
        }
        if self.topics and entry_topics & self.topics:
            return True

        entry_entities = {
            str(value).lower()
            for value in getattr(entry, "entities", None) or []
            if value
        }
        if self.entities and entry_entities & self.entities:
            return True

        entry_goals = {
            str(value).lower()
            for value in getattr(entry, "goal_ids", None) or []
            if value
        }
        return bool(self.goal_ids and entry_goals & self.goal_ids)


def extract_memory_metadata(
    *,
    question: str | None,
    answer: "RAGAnswer | None",
    intent_tags: Sequence["IntentTagPayload"] | None,
) -> MemoryMetadata:
    """Infer metadata signals for a chat turn."""

    keywords = _extract_keywords(question)
    summary = getattr(answer, "summary", None)
    if summary:
        keywords.extend(_extract_keywords(summary))

    tag_topics: list[str] = []
    goal_ids: list[str] = []
    if intent_tags:
        for tag in intent_tags:
            intent = getattr(tag, "intent", None)
            if intent:
                goal_ids.append(intent)
                tag_topics.extend(_extract_keywords(intent.replace("_", " ")))
            stance = getattr(tag, "stance", None)
            if stance:
                tag_topics.extend(_extract_keywords(stance))

    topics = _normalise_terms(keywords + tag_topics, limit=12)

    citations: Sequence["RAGCitation"] = getattr(answer, "citations", []) or []
    entities = _normalise_terms(_extract_entities(citations), limit=8)
    source_types = _normalise_terms(_extract_source_types(citations), limit=8)

    sentiment = _analyse_sentiment(keywords if summary else _extract_keywords(summary))
    if not sentiment:
        sentiment = _analyse_sentiment(keywords)

    goal_ids = _normalise_terms(goal_ids, limit=8)

    return MemoryMetadata(
        topics=topics or None,
        entities=entities or None,
        goal_ids=goal_ids or None,
        source_types=source_types or None,
        sentiment=sentiment,
    )


def _extract_keywords(text: str | None) -> list[str]:
    if not text:
        return []
    tokens = []
    for match in _TOKEN_PATTERN.findall(text):
        token = match.lower()
        if token in _STOPWORDS or len(token) < 3:
            continue
        tokens.append(token)
    return tokens


def _extract_entities(citations: Sequence["RAGCitation"]) -> list[str]:
    entities: list[str] = []
    for citation in citations:
        osis = getattr(citation, "osis", None)
        if osis:
            entities.append(str(osis))
        title = getattr(citation, "document_title", None)
        if title:
            entities.append(str(title))
    return entities


def _extract_source_types(citations: Sequence["RAGCitation"]) -> list[str]:
    source_types: list[str] = []
    for citation in citations:
        if getattr(citation, "osis", None):
            source_types.append("scripture")
        url = getattr(citation, "source_url", None)
        if url:
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            if host:
                source_types.append(host)
        document_id = getattr(citation, "document_id", None)
        if document_id:
            source_types.append("document")
    return source_types


def _analyse_sentiment(tokens: Iterable[str]) -> str | None:
    score = 0
    seen = False
    for token in tokens:
        seen = True
        if token in _POSITIVE_WORDS:
            score += 1
        elif token in _NEGATIVE_WORDS:
            score -= 1
    if not seen:
        return None
    if score > 0:
        return "positive"
    if score < 0:
        return "negative"
    return "neutral"


def _normalise_terms(values: Iterable[str], *, limit: int | None = None) -> list[str]:
    seen: set[str] = set()
    normalised: list[str] = []
    for value in values:
        if not value:
            continue
        term = str(value).strip()
        if not term:
            continue
        lowered = term.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalised.append(term)
        if limit is not None and len(normalised) >= limit:
            break
    return normalised


__all__ = ["MemoryMetadata", "MemoryFocus", "extract_memory_metadata"]
