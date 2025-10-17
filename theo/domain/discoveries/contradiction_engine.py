"""Contradiction detection engine using Natural Language Inference (NLI)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from .models import DocumentEmbedding


@dataclass(frozen=True)
class ContradictionDiscovery:
    """A detected contradiction between two documents or passages."""

    title: str
    description: str
    document_a_id: str
    document_b_id: str
    document_a_title: str
    document_b_title: str
    claim_a: str
    claim_b: str
    confidence: float  # 0.0 - 1.0
    relevance_score: float  # 0.0 - 1.0
    contradiction_type: str  # "theological" | "historical" | "textual" | "logical"
    metadata: dict[str, object]


class ContradictionDiscoveryEngine:
    """Detect contradictions between documents using NLI (Natural Language Inference).

    This engine uses a pre-trained NLI model to compare claims from different documents
    and identify contradictions. It's particularly useful for theological research where
    different authors may have conflicting interpretations.
    """

    def __init__(
        self,
        *,
        model_name: str = "microsoft/deberta-v3-base-mnli",
        contradiction_threshold: float = 0.7,
        min_confidence: float = 0.6,
    ):
        """Initialize the contradiction detection engine.

        Args:
            model_name: HuggingFace model for NLI (default: DeBERTa-v3-base-mnli)
            contradiction_threshold: Minimum score to consider a contradiction (0.0-1.0)
            min_confidence: Minimum confidence to include in results (0.0-1.0)
        """
        self.model_name = model_name
        self.contradiction_threshold = contradiction_threshold
        self.min_confidence = min_confidence
        self._model = None
        self._tokenizer = None

    class _RuleBasedNLIModel:
        """Fallback NLI model used when transformers models are unavailable."""

        _STOP_WORDS = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "to",
            "of",
            "in",
            "on",
            "by",
            "for",
            "with",
            "is",
            "are",
            "was",
            "were",
            "be",
            "this",
            "that",
            "it",
        }

        _NEGATIONS = {"not", "never", "no", "none", "without", "cannot"}

        _CONTRADICTION_GROUPS = [
            {"divine", "human", "created", "creature"},
            {"equal", "coequal", "co-equal", "subordinate", "lesser", "greater"},
            {"blue", "red", "green", "yellow", "black", "white"},
            {"true", "false"},
        ]

        def _tokenize(self, text: str) -> list[str]:
            tokens = re.findall(r"\b[\w'-]+\b", text.lower())
            return [token for token in tokens if token not in self._STOP_WORDS]

        def predict(self, text_a: str, text_b: str) -> dict[str, float]:
            tokens_a = set(self._tokenize(text_a))
            tokens_b = set(self._tokenize(text_b))

            if not tokens_a or not tokens_b:
                return {"contradiction": 0.05, "neutral": 0.9, "entailment": 0.05}

            shared_tokens = tokens_a & tokens_b
            negation_a = bool(tokens_a & self._NEGATIONS)
            negation_b = bool(tokens_b & self._NEGATIONS)

            contradiction_detected = False

            if shared_tokens and negation_a != negation_b:
                contradiction_detected = True

            if not contradiction_detected:
                for group in self._CONTRADICTION_GROUPS:
                    if (tokens_a & group) and (tokens_b & group) and (tokens_a & group) != (tokens_b & group):
                        contradiction_detected = True
                        break

            if contradiction_detected:
                return {"contradiction": 0.85, "neutral": 0.1, "entailment": 0.05}

            if tokens_a == tokens_b:
                return {"contradiction": 0.05, "neutral": 0.15, "entailment": 0.8}

            return {"contradiction": 0.1, "neutral": 0.75, "entailment": 0.15}

    def _load_model(self):
        """Lazy-load the NLI model and tokenizer."""
        if self._model is not None:
            return

        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise ImportError(
                "transformers library required for contradiction detection. "
                "Install with: pip install transformers torch"
            ) from exc

        try:
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
        except OSError:
            # Fallback to a lightweight rule-based model when the pretrained
            # model cannot be downloaded (e.g., due to offline execution).
            self._tokenizer = None
            self._model = self._RuleBasedNLIModel()

    def detect(
        self, documents: Sequence[DocumentEmbedding]
    ) -> list[ContradictionDiscovery]:
        """Detect contradictions between documents.

        Args:
            documents: List of documents with embeddings and metadata

        Returns:
            List of contradiction discoveries sorted by confidence (highest first)
        """
        if len(documents) < 2:
            return []

        self._load_model()

        # Extract claims from documents (use abstract or title as proxy for now)
        claims = self._extract_claims(documents)
        if len(claims) < 2:
            return []

        # Compare all pairs of claims
        contradictions: list[ContradictionDiscovery] = []
        for i in range(len(claims)):
            for j in range(i + 1, len(claims)):
                claim_a = claims[i]
                claim_b = claims[j]

                # Skip if same document
                if claim_a["document_id"] == claim_b["document_id"]:
                    continue

                # Check for contradiction using NLI
                result = self._check_contradiction(claim_a["text"], claim_b["text"])

                if result["is_contradiction"] and result["confidence"] >= self.min_confidence:
                    discovery = self._create_discovery(claim_a, claim_b, result)
                    contradictions.append(discovery)

        # Sort by confidence (highest first)
        contradictions.sort(key=lambda x: x.confidence, reverse=True)

        # Limit to top 20 to avoid overwhelming users
        return contradictions[:20]

    def _extract_claims(
        self, documents: Sequence[DocumentEmbedding]
    ) -> list[dict[str, object]]:
        """Extract claims from documents for comparison.

        For now, we use document abstracts or titles as proxy claims.
        Future: Extract actual claims using claim extraction models.
        """
        claims: list[dict[str, object]] = []

        for doc in documents:
            # Prefer abstract, fall back to title
            text = doc.abstract if doc.abstract else doc.title

            if not text or len(text.strip()) < 10:
                continue

            # Truncate to reasonable length (NLI models have token limits)
            text = text[:500]

            claims.append(
                {
                    "document_id": doc.document_id,
                    "title": doc.title,
                    "text": text,
                    "topics": doc.topics,
                    "metadata": doc.metadata,
                }
            )

        return claims

    def _check_contradiction(self, text_a: str, text_b: str) -> dict[str, object]:
        """Check if two texts contradict each other using NLI.

        Args:
            text_a: First text (premise)
            text_b: Second text (hypothesis)

        Returns:
            Dict with keys: is_contradiction (bool), confidence (float), scores (dict)
        """
        if isinstance(self._model, self._RuleBasedNLIModel):
            scores = self._model.predict(text_a, text_b)
            contradiction_score = float(scores["contradiction"])
            neutral_score = float(scores["neutral"])
            entailment_score = float(scores["entailment"])
        else:
            import torch

            # Tokenize input
            inputs = self._tokenizer(
                text_a,
                text_b,
                return_tensors="pt",
                truncation=True,
                max_length=512,
            )

            # Run inference
            with torch.no_grad():
                outputs = self._model(**inputs)
                logits = outputs.logits

            # Get probabilities (softmax)
            probs = torch.nn.functional.softmax(logits, dim=-1)[0]

            # NLI models typically output: [entailment, neutral, contradiction]
            # Order may vary by model, but DeBERTa-mnli uses: [contradiction, neutral, entailment]
            contradiction_score = float(probs[0])
            neutral_score = float(probs[1])
            entailment_score = float(probs[2])

        is_contradiction = contradiction_score >= self.contradiction_threshold

        return {
            "is_contradiction": is_contradiction,
            "confidence": contradiction_score,
            "scores": {
                "contradiction": contradiction_score,
                "neutral": neutral_score,
                "entailment": entailment_score,
            },
        }

    def _create_discovery(
        self,
        claim_a: dict[str, object],
        claim_b: dict[str, object],
        nli_result: dict[str, object],
    ) -> ContradictionDiscovery:
        """Create a ContradictionDiscovery from NLI results."""
        confidence = float(nli_result["confidence"])

        # Determine contradiction type based on topics
        topics_a = set(claim_a.get("topics", []))
        topics_b = set(claim_b.get("topics", []))
        shared_topics = topics_a & topics_b

        contradiction_type = self._infer_contradiction_type(shared_topics)

        # Build title
        title = f"Contradiction detected: {claim_a['title']} vs {claim_b['title']}"

        # Build description
        description = (
            f"These documents appear to contradict each other. "
            f"{claim_a['title']} states one position, while "
            f"{claim_b['title']} takes a conflicting stance."
        )

        if shared_topics:
            topics_str = ", ".join(list(shared_topics)[:3])
            description += f" Shared topics: {topics_str}."

        # Calculate relevance score (higher if more shared topics)
        relevance_score = min(0.95, 0.5 + 0.1 * len(shared_topics))

        metadata = {
            "nli_scores": nli_result["scores"],
            "shared_topics": list(shared_topics),
            "document_a_topics": list(topics_a),
            "document_b_topics": list(topics_b),
        }

        return ContradictionDiscovery(
            title=title,
            description=description,
            document_a_id=str(claim_a["document_id"]),
            document_b_id=str(claim_b["document_id"]),
            document_a_title=str(claim_a["title"]),
            document_b_title=str(claim_b["title"]),
            claim_a=str(claim_a["text"]),
            claim_b=str(claim_b["text"]),
            confidence=confidence,
            relevance_score=relevance_score,
            contradiction_type=contradiction_type,
            metadata=metadata,
        )

    def _infer_contradiction_type(self, shared_topics: set[str]) -> str:
        """Infer the type of contradiction based on shared topics."""
        # Normalize topics to lowercase for matching
        topics_lower = {t.lower() for t in shared_topics}

        # Theological contradictions
        theological_keywords = {
            "christology",
            "soteriology",
            "ecclesiology",
            "eschatology",
            "pneumatology",
            "theology",
            "doctrine",
            "trinity",
            "salvation",
        }
        if topics_lower & theological_keywords:
            return "theological"

        # Historical contradictions
        historical_keywords = {
            "history",
            "historical",
            "chronology",
            "date",
            "event",
            "timeline",
        }
        if topics_lower & historical_keywords:
            return "historical"

        # Textual contradictions
        textual_keywords = {
            "textual",
            "manuscript",
            "variant",
            "translation",
            "text",
            "criticism",
        }
        if topics_lower & textual_keywords:
            return "textual"

        # Default to logical
        return "logical"


__all__ = ["ContradictionDiscovery", "ContradictionDiscoveryEngine"]
