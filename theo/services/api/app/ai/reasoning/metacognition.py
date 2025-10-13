"""Meta-cognitive reflection and self-critique capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import math
import re
import textwrap
from typing import Iterable, Sequence

from ..clients import LanguageModelClient
from ..rag.guardrail_helpers import scrub_adversarial_language
from .fallacies import FallacyWarning, detect_fallacies


LOGGER = logging.getLogger(__name__)


DEFAULT_QUALITY_SCORE = 70
MAX_QUALITY_SCORE = 100
HIGH_FALLACY_PENALTY = 15
MEDIUM_FALLACY_PENALTY = 8
LOW_FALLACY_PENALTY = 4
WEAK_CITATION_PENALTY = 6
BIAS_WARNING_PENALTY = 10
REVISION_QUALITY_THRESHOLD = 80
LOW_QUALITY_THRESHOLD = 60
REVISION_CITATION_LIMIT = 12
REVISION_SNIPPET_TRIM = 180
_STOPWORDS = {
    "the",
    "and",
    "that",
    "this",
    "with",
    "from",
    "into",
    "have",
    "for",
    "your",
    "their",
    "shall",
    "will",
    "what",
    "when",
    "then",
    "but",
    "not",
    "can",
    "was",
    "were",
    "been",
    "has",
    "had",
    "are",
    "have",
    "having",
    "would",
    "could",
    "should",
    "might",
    "there",
    "here",
    "where",
    "because",
    "therefore",
    "also",
    "only",
    "very",
    "more",
    "most",
    "such",
    "some",
    "any",
    "each",
    "few",
    "many",
    "other",
    "another",
    "whose",
    "which",
    "who",
    "whom",
    "been",
    "do",
    "does",
    "did",
    "done",
    "being",
    "make",
    "made",
    "like",
    "just",
    "even",
    "still",
    "also",
    "god",
    "lord",
    "jesus",
    "christ",
    "spirit",
}


@dataclass(slots=True)
class Critique:
    """Self-critique of reasoning quality."""

    reasoning_quality: int  # 0-100
    fallacies_found: list[FallacyWarning] = field(default_factory=list)
    weak_citations: list[str] = field(default_factory=list)  # passage IDs
    alternative_interpretations: list[str] = field(default_factory=list)
    bias_warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RevisionResult:
    """Result of revising an answer based on critique."""

    original_answer: str
    revised_answer: str
    critique_addressed: list[str]  # Which critique points were fixed
    improvements: str
    quality_delta: int  # Change in reasoning quality score
    revised_critique: Critique


def critique_reasoning(
    reasoning_trace: str,
    answer: str,
    citations: list[dict],
) -> Critique:
    """Generate a self-critique of reasoning quality.

    Evaluates:
    - Logical fallacies
    - Citation grounding strength
    - Alternative interpretations missed
    - Perspective bias
    - Overall reasoning quality

    Args:
        reasoning_trace: The chain-of-thought reasoning
        answer: The final generated answer
        citations: Citations used

    Returns:
        Critique with quality assessment
    """
    critique = Critique(reasoning_quality=DEFAULT_QUALITY_SCORE)

    # Detect logical fallacies
    fallacies = detect_fallacies(reasoning_trace + " " + answer)
    critique.fallacies_found = fallacies

    fallacy_penalty = _calculate_fallacy_penalty(fallacies)
    if fallacy_penalty:
        LOGGER.info(
            "metacognition.apply_fallacy_penalty",
            extra={
                "fallacy_count": len(fallacies),
                "penalty": fallacy_penalty,
            },
        )

    # Check citation grounding
    weak_citations = _identify_weak_citations(answer, citations)
    critique.weak_citations = weak_citations

    weak_citation_penalty = len(weak_citations) * WEAK_CITATION_PENALTY
    if weak_citation_penalty:
        LOGGER.info(
            "metacognition.apply_citation_penalty",
            extra={
                "weak_citations": weak_citations,
                "penalty": weak_citation_penalty,
            },
        )

    # Check for perspective bias
    bias_warnings = _detect_bias(reasoning_trace, answer)
    critique.bias_warnings = bias_warnings

    bias_penalty = len(bias_warnings) * BIAS_WARNING_PENALTY
    if bias_penalty:
        LOGGER.info(
            "metacognition.apply_bias_penalty",
            extra={
                "bias_warnings": bias_warnings,
                "penalty": bias_penalty,
            },
        )

    # Surface alternative interpretations explicitly mentioned in the reasoning
    critique.alternative_interpretations = _extract_alternative_interpretations(
        reasoning_trace, answer
    )

    total_penalty = fallacy_penalty + weak_citation_penalty + bias_penalty
    critique.reasoning_quality = max(
        0,
        min(
            DEFAULT_QUALITY_SCORE - total_penalty,
            MAX_QUALITY_SCORE,
        ),
    )
    LOGGER.debug(
        "metacognition.quality_score",
        extra={
            "base": DEFAULT_QUALITY_SCORE,
            "penalty": total_penalty,
            "result": critique.reasoning_quality,
        },
    )

    # Generate recommendations
    critique.recommendations = _generate_recommendations(critique)

    return critique


def _calculate_fallacy_penalty(fallacies: Sequence[FallacyWarning]) -> int:
    """Calculate a calibrated penalty for detected fallacies.

    We penalise per fallacy type, taking the highest severity for repeated
    occurrences and adding a diminishing penalty for subsequent matches to
    avoid runaway scoring.
    """

    if not fallacies:
        return 0

    severity_weights = {
        "high": HIGH_FALLACY_PENALTY,
        "medium": MEDIUM_FALLACY_PENALTY,
        "low": LOW_FALLACY_PENALTY,
    }

    penalty = 0.0
    fallacy_counts: dict[str, int] = {}
    for fallacy in fallacies:
        weight = severity_weights.get(fallacy.severity, MEDIUM_FALLACY_PENALTY)
        count = fallacy_counts.get(fallacy.fallacy_type, 0)
        # Apply diminishing returns (log base 2) for repeated instances
        scaled_weight = weight / max(1.0, math.log2(count + 2))
        penalty += scaled_weight
        fallacy_counts[fallacy.fallacy_type] = count + 1

    return int(round(penalty))


def _identify_weak_citations(answer: str, citations: list[dict]) -> list[str]:
    """Identify citations weakly connected to claims.

    Looks for:
    - Citations mentioned but not explained
    - Vague connections ("as the Bible says...")
    - Missing context for quoted text

    Args:
        answer: Generated answer
        citations: Citations list

    Returns:
        List of passage IDs with weak connections
    """
    weak: list[str] = []
    seen: set[str] = set()

    if not answer.strip() or not citations:
        return weak

    normalised_answer = " ".join(answer.split())
    answer_lower = normalised_answer.lower()

    for citation in citations:
        normalised = _normalise_citation(citation)
        if not normalised:
            continue

        index = normalised["index"]
        marker = f"[{index}]"
        snippet = normalised["snippet"]
        passage_id = normalised["passage_id"]

        marker_positions = [m.start() for m in re.finditer(re.escape(marker), normalised_answer)]
        if not marker_positions:
            continue

        cleaned_snippet = re.sub(r"[^a-z0-9\s]", " ", snippet.lower())
        snippet_words = [
            word
            for word in cleaned_snippet.split()
            if len(word) > 3 and word not in _STOPWORDS
        ]
        if not snippet_words:
            weak.append(passage_id)
            continue

        snippet_set = set(snippet_words[:20])
        proximity_ok = False
        explanation_ok = False

        max_overlap = 0
        for position in marker_positions:
            window_start = max(0, position - 220)
            window_end = min(len(answer_lower), position + 220)
            window = answer_lower[window_start:window_end]

            overlap = sum(1 for word in snippet_set if word in window)
            if overlap >= max(1, len(snippet_set) // 4):
                proximity_ok = True
            max_overlap = max(max_overlap, overlap)

            if re.search(rf"\bexplains?\b|\bshows?\b|\bsupports?\b|\bindicates?\b", window):
                explanation_ok = True

        if not proximity_ok or (max_overlap < 2 and not explanation_ok):
            if passage_id not in seen:
                seen.add(passage_id)
                weak.append(passage_id)

    return weak


def _normalise_citation(citation: dict | None) -> dict | None:
    """Validate and normalise citation dictionaries."""

    if not citation:
        return None

    index = citation.get("index")
    snippet = citation.get("snippet")
    passage_id = citation.get("passage_id") or citation.get("document_id")

    if index in (None, "") or not isinstance(index, int) or index <= 0:
        LOGGER.debug("metacognition.skip_invalid_citation", extra={"reason": "invalid_index", "citation": citation})
        return None
    if not isinstance(snippet, str) or not snippet.strip():
        LOGGER.debug("metacognition.skip_invalid_citation", extra={"reason": "missing_snippet", "citation": citation})
        return None
    if not passage_id:
        LOGGER.debug("metacognition.skip_invalid_citation", extra={"reason": "missing_passage", "citation": citation})
        return None

    return {
        "index": index,
        "snippet": snippet.strip(),
        "passage_id": str(passage_id),
        "osis": citation.get("osis") or citation.get("document_title") or citation.get("document_id"),
        "anchor": citation.get("anchor") or citation.get("context"),
    }


def _detect_bias(reasoning_trace: str, answer: str) -> list[str]:
    """Detect perspective bias in reasoning."""

    combined_text = " ".join(f"{reasoning_trace} {answer}".split())
    if not combined_text:
        return []

    sentences = re.split(r"(?<=[.?!])\s+", combined_text)
    bias_scores = {
        "apologetic": 0.0,
        "skeptical": 0.0,
    }

    apologetic_markers = {
        "harmonious": 1.0,
        "coherent": 0.9,
        "consistent": 0.8,
        "resolve": 1.0,
        "reconcile": 1.0,
        "defend": 0.6,
        "uphold": 0.5,
    }
    skeptical_markers = {
        "contradiction": 1.0,
        "inconsistent": 0.9,
        "error": 0.5,
        "fabricated": 0.8,
        "doubt": 0.6,
        "challenge": 0.6,
        "tension": 0.4,
    }

    def _score_sentence(sentence: str, markers: dict[str, float]) -> float:
        score = 0.0
        lowered = sentence.lower()
        for marker, weight in markers.items():
            for match in re.finditer(rf"\b{re.escape(marker)}\w*\b", lowered):
                preceding = lowered[max(0, match.start() - 8) : match.start()]
                if re.search(r"\bno\b|\bnot\b|\black\b|\bwithout\b", preceding):
                    continue
                score += weight
        return score

    for sentence in sentences:
        if not sentence.strip():
            continue
        bias_scores["apologetic"] += _score_sentence(sentence, apologetic_markers)
        bias_scores["skeptical"] += _score_sentence(sentence, skeptical_markers)

    warnings: list[str] = []
    apologetic_score = bias_scores["apologetic"]
    skeptical_score = bias_scores["skeptical"]

    if apologetic_score >= 2.5 and skeptical_score < 1.0:
        warnings.append(
            "Reasoning leans heavily toward apologetic defence; engage counter-arguments."
        )
    if skeptical_score >= 3.0 and apologetic_score < 1.0:
        warnings.append(
            "Reasoning is predominantly skeptical; acknowledge constructive harmonisations."
        )

    dismissive_markers = [
        r"\bobviously\b",
        r"\bclearly\b",
        r"\bplainly\b",
    ]
    for pattern in dismissive_markers:
        if re.search(pattern, combined_text, re.IGNORECASE):
            warnings.append(
                "Overconfident language detected - provide evidential support for strong claims."
            )
            break

    if warnings:
        LOGGER.info(
            "metacognition.bias_detected",
            extra={
                "apologetic_score": round(apologetic_score, 2),
                "skeptical_score": round(skeptical_score, 2),
                "warnings": warnings,
            },
        )

    return warnings


def _extract_alternative_interpretations(reasoning_trace: str, answer: str) -> list[str]:
    """Extract alternative interpretations explicitly called out in the text."""

    combined_text = f"{reasoning_trace}\n{answer}"
    interpretations: list[str] = []
    seen: set[str] = set()

    def _add_candidate(raw: str) -> None:
        candidate = _normalise_interpretation_text(raw)
        if candidate and candidate.lower() not in seen:
            seen.add(candidate.lower())
            interpretations.append(candidate)

    for raw_line in combined_text.splitlines():
        cleaned_line = raw_line.strip()
        if not cleaned_line:
            continue

        stripped = cleaned_line.lstrip("-•").strip()
        lowered = stripped.lower()

        if "alternative interpretation" in lowered:
            if ":" in stripped:
                _, after = stripped.split(":", 1)
            else:
                after = stripped.split("interpretation", 1)[-1]
            _add_candidate(after)
            continue

        if lowered.startswith("alternatively"):
            after = stripped[len("alternatively") :]
            _add_candidate(after)
            continue

        if lowered.startswith("another interpretation"):
            if ":" in stripped:
                after = stripped.split(":", 1)[1]
            else:
                after = stripped[len("another interpretation") :]
            _add_candidate(after)
            continue

        if lowered.startswith("another possibility"):
            if ":" in stripped:
                after = stripped.split(":", 1)[1]
            else:
                after = stripped[len("another possibility") :]
            _add_candidate(after)

    # Capture inline sentences such as "Alternatively, ..." that may not be line-separated
    inline_patterns = [
        re.compile(r"\balternatively[,\s]+(?P<clause>[^.?!\n]+)", re.IGNORECASE),
        re.compile(
            r"\banother interpretation is that\s+(?P<clause>[^.?!\n]+)",
            re.IGNORECASE,
        ),
        re.compile(
            r"\banother possibility is\s+(?P<clause>[^.?!\n]+)",
            re.IGNORECASE,
        ),
    ]

    for pattern in inline_patterns:
        for match in pattern.finditer(combined_text):
            clause = match.group("clause")
            _add_candidate(clause)

    return interpretations


def _normalise_interpretation_text(text: str) -> str:
    """Normalise extracted interpretation snippets for presentation."""

    cleaned = text.strip().lstrip("-•:;").strip()
    if not cleaned:
        return ""

    # Remove leading commas or conjunctions introduced by regex captures
    cleaned = re.sub(r"^,\s*", "", cleaned)
    cleaned = re.sub(r"^(that|it|this)\s+", "", cleaned, count=1, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"^(?:is that|is|would be|might be|could be)\s+",
        "",
        cleaned,
        count=1,
        flags=re.IGNORECASE,
    )

    # Trim trailing punctuation to keep concise bullet-style entries
    cleaned = cleaned.rstrip(" .!?")

    return cleaned


def _generate_recommendations(critique: Critique) -> list[str]:
    """Generate improvement recommendations based on critique.

    Args:
        critique: The critique object

    Returns:
        List of actionable recommendations
    """
    recommendations: list[str] = []

    if critique.fallacies_found:
        recommendations.append(
            f"Address {len(critique.fallacies_found)} logical fallacies before finalizing"
        )

    if critique.weak_citations:
        recommendations.append(
            "Strengthen citation connections by explaining relevance explicitly"
        )

    if critique.bias_warnings:
        recommendations.append(
            "Re-generate answer considering alternative perspectives"
        )

    if critique.reasoning_quality < LOW_QUALITY_THRESHOLD:
        recommendations.append(
            "Reasoning quality is low - consider starting over with different approach"
        )

    if not recommendations:
        recommendations.append("Reasoning quality is acceptable - minor polish recommended")

    return recommendations


def revise_with_critique(
    original_answer: str,
    critique: Critique,
    *,
    client: LanguageModelClient,
    model: str,
    reasoning_trace: str,
    citations: list[dict],
    revised_reasoning_trace: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 800,
) -> RevisionResult:
    """Revise an answer based on critique using an LLM client.

    Args:
        original_answer: The original generated answer.
        critique: The self-critique for the original answer.
        client: Client used to call the backing language model.
        model: Identifier of the model to use for revision.
        reasoning_trace: Chain-of-thought trace associated with the answer.
        citations: Citations supplied to the original answer generation.
        revised_reasoning_trace: Optional chain-of-thought to evaluate the revision with.
        temperature: Sampling temperature for the revision call.
        max_output_tokens: Maximum tokens to request from the model.

    Returns:
        Revision result with improvements and post-revision critique.
    """

    prompt = _build_revision_prompt(original_answer, critique, citations)
    completion = client.generate(
        prompt=prompt,
        model=model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )

    revised_answer = _extract_revised_answer(completion).strip()
    if not revised_answer:
        revised_answer = original_answer

    effective_trace = revised_reasoning_trace if revised_reasoning_trace is not None else revised_answer
    if not effective_trace:
        effective_trace = reasoning_trace

    revised_critique = critique_reasoning(effective_trace, revised_answer, citations)
    critique_addressed = _compute_addressed_issues(critique, revised_critique)
    quality_delta = revised_critique.reasoning_quality - critique.reasoning_quality
    improvements = _summarise_improvements(
        critique_addressed,
        quality_delta,
        original_quality=critique.reasoning_quality,
        revised_quality=revised_critique.reasoning_quality,
    )

    return RevisionResult(
        original_answer=original_answer,
        revised_answer=revised_answer,
        critique_addressed=critique_addressed,
        improvements=improvements,
        quality_delta=quality_delta,
        revised_critique=revised_critique,
    )


def _build_revision_prompt(
    original_answer: str, critique: Critique, citations: list[dict]
) -> str:
    """Construct a structured prompt instructing the model to revise."""

    fallacies_section = _format_fallacies(critique.fallacies_found)
    weak_citations_section = _format_weak_citations(critique, citations)
    bias_section = _format_simple_list(
        critique.bias_warnings, empty_message="- None detected."
    )
    recommendations_section = _format_simple_list(
        critique.recommendations,
        empty_message="- None provided.",
    )
    selected_citations = _select_revision_citations(
        original_answer, critique, citations
    )
    citations_section = _format_citations(selected_citations)

    original_block = textwrap.indent(original_answer.strip(), "    ")

    prompt = textwrap.dedent(
        f"""
        You are a meticulous theological research assistant tasked with refining an answer
        after receiving a critique. Improve the answer while keeping it grounded in the
        provided citations and avoiding new speculative claims.

        Original answer:
        {original_block}

        Critique summary:
        - Reasoning quality: {critique.reasoning_quality}/100
        - Logical issues:
        {fallacies_section}
        - Weak or unclear citations:
        {weak_citations_section}
        - Bias warnings:
        {bias_section}
        - Recommendations:
        {recommendations_section}

        Citations available (preserve indices and ensure they support the claims):
        {citations_section}

        Revise the answer to resolve the issues above. Keep the revised answer concise
        (2-3 sentences) and end with a "Sources:" line retaining the citation indices.

        Respond strictly with the following XML structure:
        <revised_answer>...</revised_answer>
        <notes>List the key adjustments you made.</notes>
        """
    ).strip()

    return prompt


def _format_fallacies(fallacies: Iterable[FallacyWarning]) -> str:
    lines = []
    for fallacy in fallacies:
        suggestion = (
            f" Suggestion: {fallacy.suggestion}"
            if fallacy.suggestion
            else ""
        )
        lines.append(
            f"- {fallacy.fallacy_type} ({fallacy.severity}): "
            f"{fallacy.description}.{suggestion}"
        )
    if not lines:
        return "- None detected."
    return "\n".join(lines)


def _format_simple_list(values: Iterable[str], *, empty_message: str) -> str:
    items = [value.strip() for value in values if value and value.strip()]
    if not items:
        return empty_message
    return "\n".join(f"- {item}" for item in items)


def _format_weak_citations(critique: Critique, citations: list[dict]) -> str:
    if not critique.weak_citations:
        return "- None flagged."

    citation_by_id = {}
    for citation in citations:
        normalised = _normalise_citation(citation)
        if normalised:
            citation_by_id[normalised["passage_id"]] = citation

    lines: list[str] = []
    for passage_id in critique.weak_citations:
        citation = citation_by_id.get(passage_id)
        if citation:
            snippet = scrub_adversarial_language(
                (citation.get("snippet") or "").strip()
            ) or ""
            index = citation.get("index")
            osis = citation.get("osis") or citation.get("document_id") or "?"
            anchor = citation.get("anchor") or "context"
            formatted_snippet = snippet[:120] + ("…" if len(snippet) > 120 else "")
            lines.append(
                f"- Clarify how citation [{index}] {osis} ({anchor}) supports the claim: {formatted_snippet}"
            )
        else:
            lines.append(
                f"- Strengthen citation {passage_id} with clearer explanation."
            )
    return "\n".join(lines)


def _format_citations(citations: list[dict]) -> str:
    if not citations:
        return "None provided."
    lines = []
    for citation in citations[:REVISION_CITATION_LIMIT]:
        index = citation.get("index")
        snippet = scrub_adversarial_language(
            (citation.get("snippet") or "").strip()
        ) or ""
        osis = citation.get("osis") or citation.get("document_title") or citation.get("document_id") or "?"
        anchor = citation.get("anchor") or "context"
        if len(snippet) > REVISION_SNIPPET_TRIM:
            snippet = snippet[:REVISION_SNIPPET_TRIM].rstrip() + "…"
        lines.append(f"[{index}] {osis} ({anchor}) — {snippet}")
    if len(citations) > REVISION_CITATION_LIMIT:
        LOGGER.info(
            "metacognition.citation_truncation",
            extra={
                "provided": len(citations),
                "included": REVISION_CITATION_LIMIT,
            },
        )
    return "\n".join(lines)


def _select_revision_citations(
    original_answer: str, critique: Critique, citations: list[dict]
) -> list[dict]:
    """Select a manageable citation subset for revision prompts."""

    if not citations:
        return []

    answer_text = " ".join(original_answer.split())
    weak_ids = set(filter(None, critique.weak_citations))

    scored: list[tuple[int, int, int, dict]] = []
    for position, citation in enumerate(citations):
        normalised = _normalise_citation(citation)
        if not normalised:
            continue

        mentioned = f"[{normalised['index']}]" in answer_text
        priority = 0 if normalised["passage_id"] in weak_ids else 1 if mentioned else 2
        score_tuple = (
            priority,
            0 if mentioned else 1,
            position,
            citation,
        )
        scored.append(score_tuple)

    scored.sort(key=lambda item: (item[0], item[1], item[2]))
    selected = [item[3] for item in scored[:REVISION_CITATION_LIMIT]]

    return selected


def _extract_revised_answer(completion: str) -> str:
    """Extract the revised answer portion from the model completion."""

    match = re.search(
        r"<revised_answer>(?P<answer>.*?)</revised_answer>",
        completion,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        return match.group("answer").strip()

    match = re.search(r"Revised\s*Answer\s*[:\-](.*)$", completion, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()

    return completion.strip()


def _compute_addressed_issues(original: Critique, revised: Critique) -> list[str]:
    """Compare critiques and determine which issues were resolved."""

    addressed: list[str] = []

    original_fallacies = {fallacy.fallacy_type for fallacy in original.fallacies_found}
    revised_fallacies = {fallacy.fallacy_type for fallacy in revised.fallacies_found}
    for fallacy in sorted(original_fallacies - revised_fallacies):
        addressed.append(f"Resolved fallacy: {fallacy}")

    original_weak = set(filter(None, original.weak_citations))
    revised_weak = set(filter(None, revised.weak_citations))
    for passage_id in sorted(original_weak - revised_weak):
        addressed.append(f"Strengthened citation: {passage_id}")

    original_bias = set(original.bias_warnings)
    revised_bias = set(revised.bias_warnings)
    for warning in original_bias - revised_bias:
        addressed.append(f"Mitigated bias: {warning}")

    return addressed


def _summarise_improvements(
    addressed: Iterable[str],
    quality_delta: int,
    *,
    original_quality: int,
    revised_quality: int,
) -> str:
    """Build a human-readable summary of revision improvements."""

    addressed_list = list(addressed)
    summary_parts: list[str] = []

    if quality_delta > 0:
        summary_parts.append(
            f"Reasoning quality improved from {original_quality} to {revised_quality}."
        )
    elif quality_delta < 0:
        summary_parts.append(
            f"Reasoning quality decreased from {original_quality} to {revised_quality}."
        )
    else:
        summary_parts.append(
            f"Reasoning quality remained at {revised_quality}."
        )

    if addressed_list:
        summary_parts.append("Addressed: " + "; ".join(addressed_list))
    else:
        summary_parts.append("No critique items were resolved.")

    return " ".join(summary_parts)
