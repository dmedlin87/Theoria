"""Meta-cognitive reflection and self-critique capabilities."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import logging
import re
import textwrap
from typing import Iterable, Iterator

from ..clients import LanguageModelClient
from ..rag.guardrail_helpers import scrub_adversarial_language
from .fallacies import FallacyWarning, detect_fallacies


_LOGGER = logging.getLogger(__name__)


# Quality scoring configuration – calibrated constants kept in one location to
# make tuning easier and to avoid magic numbers sprinkled throughout the file.
DEFAULT_QUALITY_SCORE = 70
QUALITY_MIN = 0
QUALITY_MAX = 100
HIGH_FALLACY_PENALTY = 15
MEDIUM_FALLACY_PENALTY = 8
WEAK_CITATION_PENALTY = 5
BIAS_WARNING_PENALTY = 10


# Revision prompt configuration.
MAX_REVISION_CITATIONS = 12
REVISION_CITATION_SNIPPET_LIMIT = 180


# Expanded stopword list used when evaluating citation snippets. The list
# favours high-frequency English function words and common theological terms to
# reduce accidental overlaps.
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "god",
    "grace",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "his",
    "into",
    "is",
    "it",
    "its",
    "jesus",
    "lord",
    "may",
    "might",
    "not",
    "of",
    "on",
    "or",
    "our",
    "shall",
    "she",
    "should",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "they",
    "this",
    "those",
    "through",
    "to",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "whom",
    "why",
    "will",
    "with",
    "would",
    "you",
    "faith",
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

    unique_high = {f.fallacy_type for f in fallacies if f.severity == "high"}
    unique_medium = {f.fallacy_type for f in fallacies if f.severity == "medium"}
    fallacy_penalty = (
        len(unique_high) * HIGH_FALLACY_PENALTY
        + len(unique_medium) * MEDIUM_FALLACY_PENALTY
    )

    total_penalty = fallacy_penalty

    # Check citation grounding
    weak_citations = _identify_weak_citations(answer, citations)
    critique.weak_citations = weak_citations

    if weak_citations:
        total_penalty += len(weak_citations) * WEAK_CITATION_PENALTY

    # Check for perspective bias
    bias_warnings = _detect_bias(reasoning_trace, answer)
    critique.bias_warnings = bias_warnings

    if bias_warnings:
        total_penalty += len(bias_warnings) * BIAS_WARNING_PENALTY

    # Surface alternative interpretations explicitly mentioned in the reasoning
    critique.alternative_interpretations = _extract_alternative_interpretations(
        reasoning_trace, answer
    )

    # Clamp reasoning quality after all adjustments to the documented 0-100 range
    critique.reasoning_quality = max(
        QUALITY_MIN,
        min(DEFAULT_QUALITY_SCORE - total_penalty, QUALITY_MAX),
    )

    _log_critique_outcome(
        fallacies=fallacies,
        weak_citations=weak_citations,
        bias_warnings=bias_warnings,
        final_quality=critique.reasoning_quality,
    )

    # Generate recommendations
    critique.recommendations = _generate_recommendations(critique)

    return critique


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

    if not answer.strip() or not citations:
        return weak

    answer_lower = answer.lower()
    index_positions = {
        int(match.group(1)): match.start()
        for match in re.finditer(r"\[(\d+)\]", answer)
    }

    for citation in _iter_valid_citations(citations):
        index = citation["index"]
        passage_id = citation["passage_id"]
        snippet = citation.get("snippet", "") or ""

        if index not in index_positions:
            continue

        marker_position = index_positions[index]
        window_start = max(0, marker_position - 220)
        window_end = min(len(answer_lower), marker_position + 160)
        context_window = answer_lower[window_start:window_end]

        if not snippet.strip():
            _LOGGER.debug(
                "Citation %s has no snippet; flagging as weak", passage_id
            )
            weak.append(passage_id)
            continue

        snippet_tokens = _tokenise_snippet(snippet)
        if not snippet_tokens:
            _LOGGER.debug(
                "Citation %s snippet lacks discriminative tokens; flagging as weak",
                passage_id,
            )
            weak.append(passage_id)
            continue

        overlap = sum(1 for token in snippet_tokens if token in context_window)
        token_ratio = overlap / len(snippet_tokens)

        has_explanation = bool(
            re.search(
                r"\b(explain|support|show|demonstrate|argue|because|context)\w*",
                context_window,
            )
        )

        if token_ratio < 0.35 or (
            overlap < 2 and token_ratio < 0.75 and not has_explanation
        ):
            _LOGGER.debug(
                "Citation %s considered weak (ratio=%.2f, overlap=%s, explanation=%s)",
                passage_id,
                token_ratio,
                overlap,
                has_explanation,
            )
            weak.append(passage_id)

    # Preserve order while removing duplicates
    deduped: dict[str, None] = {}
    for passage_id in weak:
        deduped.setdefault(passage_id, None)
    return list(deduped.keys())


def _detect_bias(reasoning_trace: str, answer: str) -> list[str]:
    """Detect perspective bias in reasoning.

    Looks for:
    - Exclusively apologetic language
    - Exclusively skeptical language
    - Dismissing alternative views without engagement

    Args:
        reasoning_trace: Reasoning trace
        answer: Final answer

    Returns:
        Bias warnings
    """
    warnings: list[str] = []

    combined_text = (reasoning_trace + " " + answer).lower()
    if not combined_text.strip():
        return warnings

    balance_indicators = bool(
        re.search(
            r"\b(on the other hand|however|critics|supporters|alternatively|nevertheless)\b",
            combined_text,
        )
    )

    def _score_markers(markers: list[str]) -> int:
        score = 0
        for marker in markers:
            pattern = re.compile(rf"\b{re.escape(marker)}\b")
            for match in pattern.finditer(combined_text):
                prefix = combined_text[max(0, match.start() - 15) : match.start()]
                if re.search(r"\b(not|lack|lacks|without|question|debate|dispute)\b", prefix):
                    continue
                score += 1
        return score

    apologetic_markers = [
        "harmony",
        "harmonious",
        "coherent",
        "consistent",
        "resolves",
        "complements",
        "aligned",
        "seamless",
        "vindicates",
        "defends",
    ]
    skeptical_markers = [
        "contradiction",
        "inconsistent",
        "incoherent",
        "error",
        "impossible",
        "fabricated",
        "untenable",
        "fails",
        "undermines",
    ]

    apologetic_score = _score_markers(apologetic_markers)
    skeptical_score = _score_markers(skeptical_markers)

    if (
        apologetic_score >= 2
        and apologetic_score >= skeptical_score + 2
        and not balance_indicators
    ):
        warnings.append(
            "Reasoning shows apologetic bias - engage with skeptical objections"
        )

    if (
        skeptical_score >= 2
        and skeptical_score >= apologetic_score + 2
        and not balance_indicators
    ):
        warnings.append(
            "Reasoning shows skeptical bias - consider harmonization attempts"
        )

    dismissive_patterns = [
        re.compile(r"\b(obviously|clearly|undeniably|without question)\b"),
        re.compile(r"\bno\s+reasonable\s+(?:person|reader)\b"),
        re.compile(r"how\s+could\s+(?:anyone|someone)\s+(?:deny|doubt|question)"),
    ]
    for pattern in dismissive_patterns:
        if pattern.search(combined_text):
            warnings.append(
                "Overconfident or dismissive language detected - add supporting evidence"
            )
            break

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

    if critique.reasoning_quality < 60:
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

    selected_citations = _select_revision_citations(
        original_answer, critique, citations
    )

    fallacies_section = _format_fallacies(critique.fallacies_found)
    weak_citations_section = _format_weak_citations(critique, selected_citations)
    bias_section = _format_simple_list(
        critique.bias_warnings, empty_message="- None detected."
    )
    recommendations_section = _format_simple_list(
        critique.recommendations,
        empty_message="- None provided.",
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

        Citations available (preserve indices and ensure they support the claims).
        The list has been prioritised to keep the prompt within the model context:
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

    citation_by_id = {
        citation.get("passage_id"): citation for citation in citations if citation
    }

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
        return "- None provided."

    lines: list[str] = []
    for citation in citations:
        index = citation.get("index")
        snippet = scrub_adversarial_language(
            (citation.get("snippet") or "").strip()
        ) or ""
        if len(snippet) > REVISION_CITATION_SNIPPET_LIMIT:
            snippet = snippet[:REVISION_CITATION_SNIPPET_LIMIT].rstrip() + "…"
        osis = (
            citation.get("osis")
            or citation.get("document_title")
            or citation.get("document_id")
            or "?"
        )
        anchor = citation.get("anchor") or "context"
        lines.append(f"[{index}] {osis} ({anchor}) — {snippet}")
    return "\n".join(lines)


def _select_revision_citations(
    original_answer: str, critique: Critique, citations: list[dict]
) -> list[dict]:
    """Prioritise citations for the revision prompt.

    The selection keeps weak citations and those referenced in the original
    answer first, then fills any remaining slots with other valid citations up
    to the configured maximum. This guards against runaway prompt growth while
    ensuring the model sees the context it needs to address critique items.
    """

    valid_citations: list[dict] = []
    seen_indices: set[int] = set()
    for citation in _iter_valid_citations(citations):
        index = citation["index"]
        if index in seen_indices:
            continue
        seen_indices.add(index)
        valid_citations.append(citation)

    if not valid_citations:
        return []

    referenced_indices = {
        int(match.group(1))
        for match in re.finditer(r"\[(\d+)\]", original_answer)
    }
    weak_passage_ids = set(filter(None, critique.weak_citations))

    weak_priority: list[dict] = []
    referenced_priority: list[dict] = []
    remainder: list[dict] = []

    for citation in valid_citations:
        passage_id = citation.get("passage_id")
        index = citation["index"]
        if passage_id in weak_passage_ids:
            weak_priority.append(citation)
        elif index in referenced_indices:
            referenced_priority.append(citation)
        else:
            remainder.append(citation)

    ordered = weak_priority + referenced_priority + remainder
    if len(ordered) > MAX_REVISION_CITATIONS:
        _LOGGER.info(
            "Truncating revision citations",
            extra={
                "selected": len(ordered),
                "max": MAX_REVISION_CITATIONS,
                "weak_citations": list(weak_passage_ids),
            },
        )
    return ordered[:MAX_REVISION_CITATIONS]


def _iter_valid_citations(citations: Iterable[dict]) -> Iterator[dict]:
    """Yield citations that satisfy the minimal schema requirements."""

    for citation in citations:
        if not isinstance(citation, dict):
            _LOGGER.debug("Skipping non-dict citation entry: %r", citation)
            continue

        index = citation.get("index")
        passage_id = citation.get("passage_id")
        snippet = citation.get("snippet")

        if not isinstance(index, int) or index < 1:
            _LOGGER.debug("Skipping citation with invalid index: %r", citation)
            continue
        if not isinstance(passage_id, str) or not passage_id.strip():
            _LOGGER.debug("Skipping citation with missing passage_id: %r", citation)
            continue
        if snippet is not None and not isinstance(snippet, str):
            _LOGGER.debug("Coercing non-string snippet for citation %s", passage_id)
            citation = {**citation, "snippet": str(snippet)}

        yield citation


def _tokenise_snippet(snippet: str) -> set[str]:
    """Return discriminative tokens from a snippet for overlap checks."""

    cleaned = re.sub(r"[^a-z0-9\s]", " ", snippet.lower())
    tokens = {
        word
        for word in cleaned.split()
        if len(word) > 3 and word not in _STOPWORDS
    }
    return tokens


def _log_critique_outcome(
    *,
    fallacies: Iterable[FallacyWarning],
    weak_citations: Iterable[str],
    bias_warnings: Iterable[str],
    final_quality: int,
) -> None:
    """Emit structured logs describing the critique decision path."""

    if not _LOGGER.isEnabledFor(logging.INFO):
        return

    fallacy_summary: dict[str, int] = defaultdict(int)
    for fallacy in fallacies:
        fallacy_summary[fallacy.fallacy_type] += 1

    _LOGGER.info(
        "Metacognition critique computed",
        extra={
            "quality": final_quality,
            "fallacies": dict(fallacy_summary),
            "weak_citations": list(weak_citations),
            "bias_warnings": list(bias_warnings),
        },
    )


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
