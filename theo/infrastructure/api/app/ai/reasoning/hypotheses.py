"""Hypothesis generation and testing for theological reasoning."""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from theo.application.ports.ai_registry import GenerationError

from ...models.search import HybridSearchFilters
from ..clients import build_hypothesis_prompt
from ..rag.retrieval import PassageRetriever
from ..registry import LLMRegistry
from ..router import LLMRouterService, get_router

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


_CONFIDENCE_KEYWORDS: list[tuple[str, float]] = [
    ("certain", 0.9),
    ("definite", 0.88),
    ("strong", 0.78),
    ("likely", 0.7),
    ("probable", 0.66),
    ("plausible", 0.6),
    ("possible", 0.5),
    ("uncertain", 0.42),
    ("tentative", 0.4),
    ("speculative", 0.35),
    ("unlikely", 0.25),
    ("doubt", 0.22),
]

_SUPPORT_MARKERS = {"supports", "affirms", "confirms", "fulfills", "fulfils", "therefore"}
_CONTRADICTION_MARKERS = {
    "contradicts",
    "contrary",
    "refutes",
    "refute",
    "challenge",
    "challenges",
    "challenging",
    "disputes",
    "undermines",
    "against",
    "opposes",
    "however",
    "nevertheless",
    "yet",
    "but",
    "tension",
}
_NEGATION_MARKERS = {"not", "never", "no", "without"}
_DEFAULT_PERSPECTIVE_KEYS = ("apologetic", "skeptical", "neutral")


@dataclass(slots=True)
class PassageRef:
    """Reference to a supporting/contradicting passage."""

    passage_id: str
    osis: str
    snippet: str
    relevance_score: float  # 0.0 - 1.0


@dataclass(slots=True)
class Hypothesis:
    """A testable theological hypothesis."""

    id: str
    claim: str
    confidence: float  # 0.0 - 1.0
    supporting_passages: list[PassageRef] = field(default_factory=list)
    contradicting_passages: list[PassageRef] = field(default_factory=list)
    fallacy_warnings: list[str] = field(default_factory=list)
    perspective_scores: dict[str, float] = field(
        default_factory=dict
    )  # skeptical/apologetic/neutral
    status: str = "active"  # active | confirmed | refuted | uncertain
    last_test: "HypothesisTest | None" = None


@dataclass(slots=True)
class HypothesisTest:
    """Result of testing a hypothesis with additional evidence."""

    hypothesis_id: str
    new_passages_found: int
    confidence_delta: float  # Change in confidence
    updated_confidence: float
    recommendation: str  # "confirm" | "refute" | "gather_more" | "uncertain"
    supporting_added: int = 0
    contradicting_added: int = 0


class HypothesisGenerator:
    """Generates competing hypotheses from theological evidence."""

    def __init__(
        self,
        session: Session,
        *,
        router: LLMRouterService | None = None,
        registry: LLMRegistry | None = None,
        model_hint: str | None = None,
        persona: str = "analyst",
    ) -> None:
        self.session = session
        self._router = router
        self._registry = registry
        self._model_hint = model_hint
        self.persona = persona

    # ------------------------------------------------------------------
    # Hypothesis generation
    # ------------------------------------------------------------------
    def generate_from_question(
        self,
        question: str,
        passages: Sequence[Mapping[str, Any] | Any],
        max_hypotheses: int = 4,
    ) -> list[Hypothesis]:
        """Generate 2-4 competing hypotheses from a theological question."""

        prompt = build_hypothesis_prompt(
            question,
            passages,
            persona=self.persona,
            max_hypotheses=max_hypotheses,
        )
        router = self._resolve_router()
        hypotheses: list[Hypothesis] = []
        if router is not None:
            candidates = list(
                router.iter_candidates("hypothesis_generation", self._model_hint)
            )
            for candidate in candidates:
                try:
                    routed_generation = router.execute_generation(
                        workflow="hypothesis_generation",
                        model=candidate,
                        prompt=prompt,
                        temperature=0.3,
                        max_output_tokens=900,
                    )
                except GenerationError as exc:
                    logger.warning(
                        "Hypothesis generation failed via %s: %s",
                        candidate.name,
                        exc,
                    )
                    continue
                hypotheses = self._parse_completion(
                    routed_generation.output, passages, max_hypotheses
                )
                if hypotheses:
                    break
        if not hypotheses:
            logger.debug("Falling back to heuristic hypotheses for %s", question)
            hypotheses = self._fallback_hypotheses(question, passages, max_hypotheses)
        return hypotheses[:max_hypotheses]

    def extract_from_reasoning(self, reasoning_trace: str) -> list[Hypothesis]:
        """Extract implicit hypotheses from reasoning trace."""

        if not reasoning_trace:
            return []

        hypotheses: list[Hypothesis] = []
        seen_claims: set[str] = set()

        patterns: list[tuple[str, float]] = [
            (r"(?i)one\s+possibility\s+is\s+that\s+(?P<claim>[^.?!]+)", 0.55),
            (r"(?i)one\s+possibility\s+is\s+(?P<claim>[^.?!]+)", 0.52),
            (r"(?i)alternatively[,\s]+(?P<claim>[^.?!]+)", 0.48),
            (r"(?i)another\s+hypothesis\s+is\s+that\s+(?P<claim>[^.?!]+)", 0.5),
            (r"(?i)this\s+could\s+mean\s+that\s+(?P<claim>[^.?!]+)", 0.5),
            (r"(?i)it\s+may\s+be\s+that\s+(?P<claim>[^.?!]+)", 0.45),
            (r"(?i)hypothesis\s*:\s*(?P<claim>[^.?!]+)", 0.58),
        ]

        for pattern, base_conf in patterns:
            for match in re.finditer(pattern, reasoning_trace):
                claim = match.group("claim").strip(" .;:-")
                if len(claim) < 8:
                    continue
                normalized = claim.lower()
                if normalized in seen_claims:
                    continue
                window_start = max(match.start() - 120, 0)
                window_end = min(match.end() + 120, len(reasoning_trace))
                context = reasoning_trace[window_start:window_end]
                confidence = _confidence_from_language(context) or base_conf
                perspective = _infer_perspective_scores(context)
                references = _extract_citation_refs(match.group(0))
                fallacies = _detect_fallacy_language(context)
                hypothesis = Hypothesis(
                    id=_make_hypothesis_id(len(hypotheses) + 1),
                    claim=claim,
                    confidence=_clamp(confidence),
                    supporting_passages=references,
                    fallacy_warnings=fallacies,
                    perspective_scores=perspective,
                )
                hypotheses.append(hypothesis)
                seen_claims.add(normalized)

        if hypotheses:
            return hypotheses

        # Fallback: parse bullet lists or enumerated lines mentioning hypotheses
        for line in reasoning_trace.splitlines():
            stripped = line.strip(" -*\t")
            lowered = stripped.lower()
            if not stripped:
                continue
            if "hypothesis" not in lowered and "possibility" not in lowered:
                continue
            claim = stripped.split(":", 1)[-1].strip()
            if len(claim) < 8:
                continue
            normalized = claim.lower()
            if normalized in seen_claims:
                continue
            hypotheses.append(
                Hypothesis(
                    id=_make_hypothesis_id(len(hypotheses) + 1),
                    claim=claim,
                    confidence=0.5,
                    perspective_scores={"neutral": 0.55},
                    fallacy_warnings=[],
                )
            )
            seen_claims.add(normalized)

        return hypotheses

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _resolve_router(self) -> LLMRouterService | None:
        if self._router is not None:
            return self._router
        try:
            self._router = get_router(self.session, registry=self._registry)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Unable to resolve LLM router: %s", exc)
            self._router = None
        return self._router

    def _parse_completion(
        self,
        completion: str,
        passages: Sequence[Mapping[str, Any] | Any],
        max_hypotheses: int,
    ) -> list[Hypothesis]:
        payload = _extract_json_payload(completion)
        if payload is None:
            return []

        if isinstance(payload, Mapping):
            items = payload.get("hypotheses")
            if isinstance(items, list):
                raw_items = items
            else:
                raw_items = [payload]
        elif isinstance(payload, list):
            raw_items = payload
        else:
            return []

        lookup_index, lookup_id = _build_passage_lookups(passages)
        hypotheses: list[Hypothesis] = []
        for idx, item in enumerate(raw_items, start=1):
            if not isinstance(item, Mapping):
                claim = str(item).strip()
                if not claim:
                    continue
                hypotheses.append(
                    Hypothesis(
                        id=_make_hypothesis_id(idx),
                        claim=claim,
                        confidence=0.55,
                        perspective_scores={"neutral": 0.5},
                    )
                )
                continue

            claim = str(item.get("claim") or item.get("hypothesis") or "").strip()
            if not claim:
                continue

            hypothesis_id = str(item.get("id") or _make_hypothesis_id(idx))
            confidence = _coerce_confidence(item.get("confidence"))
            supporting_refs = _gather_passage_refs(
                lookup_index,
                lookup_id,
                item.get("supporting_indices"),
                item.get("supporting_passages"),
                item.get("supporting"),
            )
            contradicting_refs = _gather_passage_refs(
                lookup_index,
                lookup_id,
                item.get("contradicting_indices"),
                item.get("contradicting_passages"),
                item.get("contradicting"),
            )
            fallacy_notes = item.get("fallacy_notes") or item.get("fallacies") or []
            perspective_scores = _normalise_perspective_scores(
                item.get("perspective_scores")
            )
            status = str(item.get("status") or "active")
            hypotheses.append(
                Hypothesis(
                    id=hypothesis_id,
                    claim=claim,
                    confidence=_clamp(confidence),
                    supporting_passages=supporting_refs,
                    contradicting_passages=contradicting_refs,
                    fallacy_warnings=[
                        str(note).strip() for note in fallacy_notes if str(note).strip()
                    ],
                    perspective_scores=perspective_scores,
                    status=status,
                )
            )
            if len(hypotheses) >= max_hypotheses:
                break

        return hypotheses

    def _fallback_hypotheses(
        self,
        question: str,
        passages: Sequence[Mapping[str, Any] | Any],
        max_hypotheses: int,
    ) -> list[Hypothesis]:
        claims: list[str] = []
        seen: set[str] = set()
        for raw in passages:
            if isinstance(raw, Mapping):
                snippet = str(raw.get("snippet") or raw.get("text") or "").strip()
            else:
                snippet = str(getattr(raw, "snippet", getattr(raw, "text", ""))).strip()
            if not snippet:
                continue
            first_sentence = _first_sentence(snippet)
            normalized = first_sentence.lower()
            if normalized in seen:
                continue
            claims.append(first_sentence)
            seen.add(normalized)
            if len(claims) >= max_hypotheses:
                break

        if not claims:
            cleaned_question = question.strip().rstrip("?")
            if cleaned_question:
                claims = [
                    f"Scripture offers multiple interpretations of {cleaned_question}.",
                    f"Counter-evidence may exist regarding {cleaned_question}.",
                ]
            else:
                claims = ["The evidence base is currently insufficient to state a conclusion."]

        hypotheses: list[Hypothesis] = []
        for idx, claim in enumerate(claims[:max_hypotheses], start=1):
            hypotheses.append(
                Hypothesis(
                    id=f"fallback-{idx}",
                    claim=claim,
                    confidence=0.45 if idx == 1 else 0.4,
                    perspective_scores={"neutral": 0.5},
                    fallacy_warnings=["Generated via heuristic fallback"],
                )
            )
        return hypotheses


def test_hypothesis(
    hypothesis: Hypothesis,
    session: Session,
    retrieval_budget: int = 10,
) -> HypothesisTest:
    """Test a hypothesis by retrieving additional evidence."""

    retriever = PassageRetriever(session)
    results = retriever.search(
        query=hypothesis.claim,
        osis=None,
        filters=HybridSearchFilters(),
        k=retrieval_budget,
    )

    existing_ids = {
        ref.passage_id for ref in hypothesis.supporting_passages
    } | {ref.passage_id for ref in hypothesis.contradicting_passages}

    new_supporting: list[PassageRef] = []
    new_contradicting: list[PassageRef] = []

    for result in results:
        passage_id = str(getattr(result, "id", uuid.uuid4().hex))
        if passage_id in existing_ids:
            continue
        snippet = str(getattr(result, "snippet", getattr(result, "text", ""))).strip()
        classification = _classify_passage_evidence(hypothesis.claim, snippet)
        if classification == "neutral":
            continue
        score_value = getattr(result, "score", None)
        ref = PassageRef(
            passage_id=passage_id,
            osis=str(getattr(result, "osis_ref", "Unknown") or "Unknown"),
            snippet=snippet or "[No snippet provided]",
            relevance_score=_clamp(
                float(score_value) if isinstance(score_value, (int, float)) else 0.6
            ),
        )
        if classification == "support":
            new_supporting.append(ref)
        else:
            new_contradicting.append(ref)
        existing_ids.add(passage_id)

    previous_confidence = hypothesis.confidence
    updated_confidence = update_hypothesis_confidence(
        hypothesis, new_supporting, new_contradicting
    )

    hypothesis.supporting_passages.extend(new_supporting)
    hypothesis.contradicting_passages.extend(new_contradicting)
    hypothesis.confidence = updated_confidence

    new_passages_found = len(new_supporting) + len(new_contradicting)
    confidence_delta = updated_confidence - previous_confidence

    if updated_confidence >= 0.8 and len(new_supporting) > len(new_contradicting):
        recommendation = "confirm"
    elif updated_confidence <= 0.25 and len(new_contradicting) >= len(new_supporting):
        recommendation = "refute"
    elif new_passages_found == 0:
        recommendation = "uncertain"
    else:
        recommendation = "gather_more"

    status_map = {
        "confirm": "confirmed",
        "refute": "refuted",
        "gather_more": "active",
        "uncertain": "uncertain",
    }
    hypothesis.status = status_map.get(recommendation, hypothesis.status)

    test_result = HypothesisTest(
        hypothesis_id=hypothesis.id,
        new_passages_found=new_passages_found,
        confidence_delta=confidence_delta,
        updated_confidence=updated_confidence,
        recommendation=recommendation,
        supporting_added=len(new_supporting),
        contradicting_added=len(new_contradicting),
    )
    hypothesis.last_test = test_result

    return test_result


def update_hypothesis_confidence(
    hypothesis: Hypothesis,
    new_supporting: list[PassageRef],
    new_contradicting: list[PassageRef],
) -> float:
    """Update hypothesis confidence using Bayesian-style heuristics."""

    current_confidence = hypothesis.confidence

    support_boost = sum(ref.relevance_score * 0.15 for ref in new_supporting)
    contradict_penalty = sum(ref.relevance_score * 0.18 for ref in new_contradicting)

    updated = current_confidence + support_boost - contradict_penalty

    return _clamp(updated)


# ----------------------------------------------------------------------
# Helper utilities
# ----------------------------------------------------------------------

def _extract_json_payload(completion: str) -> Any | None:
    if not completion:
        return None
    completion = completion.strip()
    try:
        return json.loads(completion)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for idx, char in enumerate(completion):
            if char not in "[{":
                continue
            try:
                obj, _ = decoder.raw_decode(completion[idx:])
                return obj
            except json.JSONDecodeError:
                continue
    return None


def _build_passage_lookups(
    passages: Sequence[Mapping[str, Any] | Any],
) -> tuple[dict[int, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_index: dict[int, dict[str, Any]] = {}
    by_id: dict[str, dict[str, Any]] = {}
    for idx, raw in enumerate(passages, start=1):
        if isinstance(raw, Mapping):
            passage_id = str(raw.get("id") or raw.get("passage_id") or idx)
            osis = str(raw.get("osis") or raw.get("osis_ref") or "Unknown")
            snippet = str(raw.get("snippet") or raw.get("text") or "")
            score = raw.get("score")
        else:
            passage_id = str(
                getattr(raw, "passage_id", getattr(raw, "id", idx))
            )
            osis = str(
                getattr(raw, "osis", getattr(raw, "osis_ref", "Unknown"))
            )
            snippet = str(getattr(raw, "snippet", getattr(raw, "text", "")))
            score = getattr(raw, "score", None)
        relevance = (
            float(score)
            if isinstance(score, (int, float))
            else 0.6
        )
        entry = {
            "passage_id": passage_id,
            "osis": osis or "Unknown",
            "snippet": snippet.strip(),
            "relevance": _clamp(relevance),
        }
        by_index[idx] = entry
        by_id[passage_id] = entry
    return by_index, by_id


def _gather_passage_refs(
    lookup_index: Mapping[int, Mapping[str, Any]],
    lookup_id: Mapping[str, Mapping[str, Any]],
    *containers: Any,
) -> list[PassageRef]:
    refs: list[PassageRef] = []
    seen: set[str] = set()
    for container in containers:
        if not container:
            continue
        if isinstance(container, Mapping):
            iterable: Iterable[Any] = [container]
        elif isinstance(container, (str, bytes)):
            iterable = [container]
        elif isinstance(container, Iterable):
            iterable = container
        else:
            iterable = [container]
        for item in iterable:
            entry: dict[str, Any] | None = None
            if isinstance(item, Mapping):
                index = item.get("index")
                if index is not None:
                    try:
                        entry = dict(lookup_index.get(int(index)) or {})
                    except (TypeError, ValueError):
                        entry = None
                if not entry:
                    passage_id = item.get("id") or item.get("passage_id")
                    if passage_id is not None:
                        entry = dict(lookup_id.get(str(passage_id)) or {})
                if not entry:
                    entry = {
                        "passage_id": str(
                            item.get("id")
                            or item.get("passage_id")
                            or f"ref-{uuid.uuid4().hex[:6]}"
                        ),
                        "osis": str(item.get("osis") or item.get("osis_ref") or "Unknown"),
                        "snippet": str(item.get("snippet") or item.get("text") or ""),
                        "relevance": _clamp(
                            float(item.get("relevance") or item.get("score") or 0.6)
                        ),
                    }
            else:
                entry = None
                try:
                    numeric = int(item)
                except (TypeError, ValueError):
                    numeric = None
                if numeric is not None:
                    entry = dict(lookup_index.get(numeric) or {})
                if not entry:
                    entry = dict(lookup_id.get(str(item)) or {})
                if not entry:
                    continue
            passage_id = str(entry.get("passage_id") or f"ref-{uuid.uuid4().hex[:6]}")
            if passage_id in seen:
                continue
            seen.add(passage_id)
            refs.append(
                PassageRef(
                    passage_id=passage_id,
                    osis=str(entry.get("osis") or "Unknown"),
                    snippet=str(entry.get("snippet") or "").strip(),
                    relevance_score=_clamp(float(entry.get("relevance", 0.6))),
                )
            )
    return refs


def _normalise_perspective_scores(raw: Any) -> dict[str, float]:
    scores: dict[str, float] = {}
    if isinstance(raw, Mapping):
        for key in _DEFAULT_PERSPECTIVE_KEYS:
            value = raw.get(key)
            if isinstance(value, (int, float)):
                scores[key] = _clamp(float(value))
    if not scores:
        scores = {"neutral": 0.5}
    return scores


def _coerce_confidence(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip().lower()
        if stripped.endswith("%"):
            try:
                return float(stripped[:-1]) / 100.0
            except ValueError:
                pass
        for keyword, score in _CONFIDENCE_KEYWORDS:
            if keyword in stripped:
                return score
        try:
            return float(stripped)
        except ValueError:
            return 0.55
    return 0.55


def _confidence_from_language(text: str) -> float | None:
    lowered = text.lower()
    for keyword, score in _CONFIDENCE_KEYWORDS:
        if keyword in lowered:
            return score
    return None


def _extract_citation_refs(segment: str) -> list[PassageRef]:
    refs: list[PassageRef] = []
    for match in re.findall(r"\[(\d+)\]", segment):
        passage_id = f"trace-{match}"
        refs.append(
            PassageRef(
                passage_id=passage_id,
                osis=f"citation[{match}]",
                snippet=f"Evidence referenced via citation [{match}]",
                relevance_score=0.35,
            )
        )
    return refs


def _detect_fallacy_language(text: str) -> list[str]:
    fallacies: list[str] = []
    lowered = text.lower()
    if "obviously" in lowered or "clearly" in lowered:
        fallacies.append("Watch for overstatement; evidence may be asserted as obvious.")
    if "therefore it must" in lowered or "must be true" in lowered:
        fallacies.append("Check for necessity claims without warrant.")
    return fallacies


def _infer_perspective_scores(text: str) -> dict[str, float]:
    lowered = text.lower()
    scores = {"neutral": 0.5, "apologetic": 0.4, "skeptical": 0.4}
    if any(token in lowered for token in ("reconcile", "harmonize", "harmonise")):
        scores["apologetic"] = 0.7
    if any(token in lowered for token in ("doubt", "skeptic", "challenge")):
        scores["skeptical"] = 0.65
    if "balanced" in lowered or "consider both" in lowered:
        scores["neutral"] = 0.65
    return {k: _clamp(v) for k, v in scores.items()}


def _make_hypothesis_id(index: int) -> str:
    return f"hypothesis-{index}-{uuid.uuid4().hex[:6]}"


def _first_sentence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    match = re.search(r"[^.!?]+[.!?]?", stripped)
    if match:
        return match.group(0).strip()
    return stripped


def _classify_passage_evidence(claim: str, snippet: str) -> str:
    if not snippet:
        return "neutral"
    lowered = snippet.lower()
    claim_terms = {
        term
        for term in re.findall(r"[a-zA-Z']+", claim.lower())
        if len(term) >= 4
    }
    if not claim_terms:
        return "neutral"
    stems = {term.rstrip("s") for term in claim_terms if len(term) > 4}
    overlap = sum(1 for term in claim_terms if term in lowered)
    stem_overlap = sum(1 for stem in stems if stem and stem in lowered)
    has_overlap = (overlap + stem_overlap) > 0
    negation_present = any(marker in lowered for marker in _NEGATION_MARKERS)
    contradiction_marker_present = any(
        marker in lowered for marker in _CONTRADICTION_MARKERS
    )

    if any(
        re.search(rf"not\s+{re.escape(term)}", lowered) for term in claim_terms | stems
    ):
        return "contradiction"
    if negation_present and contradiction_marker_present:
        return "contradiction"
    if negation_present and has_overlap:
        return "contradiction"
    if contradiction_marker_present and has_overlap:
        return "contradiction"
    if not has_overlap:
        return "neutral"
    if contradiction_marker_present:
        return "contradiction"
    if any(marker in lowered for marker in _SUPPORT_MARKERS):
        return "support"
    if negation_present:
        return "contradiction"
    threshold = max(1, len(claim_terms) // 3)
    return "support" if overlap >= threshold else "neutral"


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


__all__ = [
    "Hypothesis",
    "HypothesisGenerator",
    "HypothesisTest",
    "PassageRef",
    "test_hypothesis",
    "update_hypothesis_confidence",
]
