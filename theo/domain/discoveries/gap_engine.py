"""Gap detection engine leveraging BERTopic against curated theology topics."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .models import DocumentEmbedding

try:  # pragma: no cover - optional dependency
    import yaml
except ImportError:  # pragma: no cover - exercised in tests when dependency missing
    yaml = None  # type: ignore[assignment]


@dataclass(frozen=True)
class GapDiscovery:
    """A surfaced gap where the corpus under-indexes a theological topic."""

    title: str
    description: str
    reference_topic: str
    missing_keywords: list[str]
    shared_keywords: list[str]
    related_documents: list[str]
    confidence: float
    relevance_score: float
    metadata: Mapping[str, Any] = field(default_factory=dict)


class GapDiscoveryEngine:
    """Identify theological gaps by comparing corpus topics with reference themes."""

    def __init__(
        self,
        *,
        reference_topics_path: str | Path | None = None,
        min_similarity: float = 0.35,
        max_results: int = 10,
        topic_model: Any | None = None,
        reference_topics: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        self.reference_topics_path = (
            Path(reference_topics_path)
            if reference_topics_path is not None
            else Path(__file__).resolve().parents[3]
            / "data"
            / "seeds"
            / "theological_topics.yaml"
        )
        self.min_similarity = float(min_similarity)
        self.max_results = int(max_results)
        self._topic_model = topic_model
        self._reference_topics_override = (
            list(reference_topics) if reference_topics is not None else None
        )
        self._reference_topics_cache: list[dict[str, Any]] | None = None

    def detect(self, documents: Sequence[DocumentEmbedding]) -> list[GapDiscovery]:
        """Detect gaps between user documents and curated theological topics."""

        reference_topics = self._load_reference_topics()
        if not reference_topics:
            return []

        corpus_docs: list[DocumentEmbedding] = []
        texts: list[str] = []
        for doc in documents:
            text = self._prepare_document_text(doc)
            if text:
                corpus_docs.append(doc)
                texts.append(text)
        if not corpus_docs:
            return []

        topic_model = self._ensure_topic_model()
        topics, _ = topic_model.fit_transform(texts)

        topic_keywords: dict[int, set[str]] = {}
        topic_documents: dict[int, list[DocumentEmbedding]] = {}
        for index, topic_id in enumerate(topics):
            topic_documents.setdefault(topic_id, []).append(corpus_docs[index])
            if topic_id not in topic_keywords:
                keywords = topic_model.get_topic(topic_id)
                if not keywords:
                    topic_keywords[topic_id] = set()
                    continue
                topic_keywords[topic_id] = {
                    str(keyword).strip().lower()
                    for keyword, _ in keywords[:10]
                    if str(keyword).strip()
                }

        discoveries: list[GapDiscovery] = []
        for topic in reference_topics:
            ref_keywords = set(topic["keywords"])
            if not ref_keywords:
                continue
            best_topic_id: int | None = None
            best_similarity = 0.0
            best_shared: set[str] = set()
            for topic_id, keywords in topic_keywords.items():
                if not keywords:
                    continue
                shared = ref_keywords & keywords
                if not shared:
                    continue
                similarity = len(shared) / len(ref_keywords | keywords)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_topic_id = topic_id
                    best_shared = shared
            if best_similarity >= self.min_similarity:
                continue

            missing_keywords = sorted(ref_keywords - best_shared)
            shared_keywords = sorted(best_shared)
            coverage_ratio = 0.0
            if ref_keywords:
                coverage_ratio = len(shared_keywords) / len(ref_keywords)
            gap_intensity = 1.0 - coverage_ratio
            if self.min_similarity > 0.0:
                gap_ratio = min(
                    1.0,
                    max(self.min_similarity - best_similarity, 0.0) / self.min_similarity,
                )
            else:
                gap_ratio = gap_intensity
            confidence_base = 0.55 + 0.35 * gap_intensity + 0.2 * gap_ratio
            confidence = round(min(0.95, max(0.5, confidence_base)), 4)
            missing_ratio = len(missing_keywords) / max(len(ref_keywords), 1)
            relevance_base = 0.45 + 0.4 * missing_ratio
            if best_topic_id is None:
                relevance_base += 0.05
            relevance = round(min(0.9, max(0.45, relevance_base)), 4)

            if best_topic_id is None:
                related_docs: list[str] = []
            else:
                related_docs = [
                    doc.document_id for doc in topic_documents.get(best_topic_id, [])
                ]

            description_parts = [
                f"The current corpus shows limited engagement with {topic['name']}.",
            ]
            if topic["summary"]:
                description_parts.append(topic["summary"])
            if missing_keywords:
                description_parts.append(
                    "Key theological motifs absent include "
                    + ", ".join(missing_keywords[:5])
                    + (" and more" if len(missing_keywords) > 5 else "")
                )
            description = " ".join(description_parts).strip()

            metadata = {
                "gapData": {
                    "referenceTopic": topic["name"],
                    "referenceSummary": topic["summary"],
                    "missingKeywords": missing_keywords,
                    "sharedKeywords": shared_keywords,
                    "scriptureReferences": topic["scriptures"],
                    "coverageRatio": round(coverage_ratio, 4),
                    "gapIntensity": round(gap_intensity, 4),
                    "similarityScore": round(best_similarity, 4),
                    "thresholdSimilarity": round(self.min_similarity, 4),
                    "missingCount": len(missing_keywords),
                    "sharedCount": len(shared_keywords),
                    "bestMatchTopicId": best_topic_id,
                },
                "relatedDocuments": related_docs,
                "relatedTopics": shared_keywords,
            }

            discoveries.append(
                GapDiscovery(
                    title=f"Gap detected: {topic['name']}",
                    description=description,
                    reference_topic=topic["name"],
                    missing_keywords=missing_keywords,
                    shared_keywords=shared_keywords,
                    related_documents=related_docs,
                    confidence=confidence,
                    relevance_score=relevance,
                    metadata=metadata,
                )
            )

        discoveries.sort(key=lambda item: item.confidence, reverse=True)
        if self.max_results > 0:
            discoveries = discoveries[: self.max_results]
        return discoveries

    def _ensure_topic_model(self) -> Any:
        if self._topic_model is not None:
            return self._topic_model
        try:  # pragma: no cover - requires optional dependency in runtime
            from bertopic import BERTopic
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "bertopic library required for gap detection. Install with: pip install bertopic"
            ) from exc
        self._topic_model = BERTopic()
        return self._topic_model

    def _load_reference_topics(self) -> list[dict[str, Any]]:
        if self._reference_topics_cache is not None:
            return self._reference_topics_cache
        if self._reference_topics_override is not None:
            payload = [self._normalise_reference_topic(item) for item in self._reference_topics_override]
            self._reference_topics_cache = [item for item in payload if item["name"] and item["keywords"]]
            return self._reference_topics_cache
        path = Path(self.reference_topics_path)
        if not path.exists():
            self._reference_topics_cache = []
            return self._reference_topics_cache
        if yaml is None:  # pragma: no cover - runtime guard
            raise ImportError(
                "pyyaml is required to load theological reference topics. Install with: pip install pyyaml"
            )
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or []
        payload = [self._normalise_reference_topic(item) for item in data]
        self._reference_topics_cache = [item for item in payload if item["name"] and item["keywords"]]
        return self._reference_topics_cache

    def _normalise_reference_topic(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        name = str(raw.get("name", "")).strip()
        summary = str(raw.get("summary", "")).strip()
        keywords_raw = raw.get("keywords") or raw.get("tags") or []
        keywords = self._coerce_keywords(keywords_raw)
        scriptures_raw = raw.get("scriptures") or raw.get("references") or []
        scriptures = [
            str(item).strip()
            for item in scriptures_raw
            if isinstance(item, str) and str(item).strip()
        ]
        return {
            "name": name,
            "summary": summary,
            "keywords": keywords,
            "scriptures": scriptures,
        }

    @staticmethod
    def _coerce_keywords(raw: object) -> list[str]:
        keywords: list[str] = []
        if isinstance(raw, str):
            raw_values = [raw]
        elif isinstance(raw, Mapping):
            raw_values = [item for item in list(raw.keys()) + list(raw.values()) if isinstance(item, str)]
        elif isinstance(raw, Sequence):
            raw_values = [item for item in raw if isinstance(item, str)]
        else:
            raw_values = []
        for keyword in raw_values:
            token = keyword.strip().lower()
            if token and token not in keywords:
                keywords.append(token)
        return keywords

    @staticmethod
    def _prepare_document_text(document: DocumentEmbedding) -> str:
        parts: list[str] = []
        if document.title and document.title.strip():
            parts.append(document.title.strip())
        if document.abstract and document.abstract.strip():
            parts.append(document.abstract.strip())
        if not parts and document.topics:
            parts.extend([topic for topic in document.topics if isinstance(topic, str) and topic.strip()])
        text = " ".join(parts).strip()
        return text


__all__ = ["GapDiscovery", "GapDiscoveryEngine"]
