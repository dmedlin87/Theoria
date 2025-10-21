"""Meta-cognitive reflection and self-critique capabilities."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import logging
import re
import textwrap
from typing import Iterable

from ..clients import LanguageModelClient
from ..rag.guardrail_helpers import scrub_adversarial_language
from .fallacies import FallacyWarning, detect_fallacies

LOGGER = logging.getLogger(__name__)


DEFAULT_QUALITY_SCORE = 90
MIN_QUALITY_SCORE = 0
MAX_QUALITY_SCORE = 100
# A single high-severity fallacy should substantially lower the quality score so
# that critiques surface the issue prominently. 15 points still left obviously
# flawed reasoning rated too highly (see tests/api/ai/test_reasoning_modules.py).
# Increase the penalty so one severe fallacy drops the score below 70.
HIGH_FALLACY_PENALTY = 25
MEDIUM_FALLACY_PENALTY = 8
WEAK_CITATION_PENALTY = 5
BIAS_WARNING_PENALTY = 10
LOW_QUALITY_THRESHOLD = 60
REVISION_QUALITY_THRESHOLD = 80
CITATION_CONTEXT_WINDOW_CHARS = 180
MIN_SNIPPET_KEYWORDS = 2
MAX_CITATIONS_IN_PROMPT = 12
MAX_CITATION_SECTION_CHARS = 2000
BIAS_DOMINANCE_RATIO = 0.6

NEGATION_WORDS = {
    "no",
    "not",
    "without",
    "lack",
    "lacking",
    "hardly",
    "scarcely",
    "barely",
}

APOLOGETIC_MARKERS = {
    "harmony",
    "harmonious",
    "coherent",
    "consistent",
    "resolves",
    "complements",
    "aligned",
    "seamless",
    "upholds",
    "confirms",
}

SKEPTICAL_MARKERS = {
    "contradiction",
    "inconsistent",
    "incoherent",
    "error",
    "impossible",
    "fabricated",
    "problematic",
}


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
    "are",
    "has",
    "had",
    "because",
    "therefore",
    "hence",
    "thus",
    "also",
    "upon",
    "unto",
    "about",
    "among",
    "after",
    "before",
    "might",
    "should",
    "would",
    "could",
    "god",
    "lord",
    "jesus",
}


@dataclass(slots=True)
class CitationRecord:
    """Validated citation used for reasoning analysis."""

    index: int
    passage_id: str
    snippet: str
    raw: dict


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

    combined_text = f"{reasoning_trace}\n{answer}".strip()

    # Detect logical fallacies
    fallacies = detect_fallacies(combined_text)
    critique.fallacies_found = fallacies

    high_fallacies = sum(1 for f in fallacies if f.severity == "high")
    medium_fallacies = sum(1 for f in fallacies if f.severity == "medium")

    if fallacies:
        LOGGER.info(
            "Detected %s fallacies (high=%s, medium=%s) during critique",
            len(fallacies),
            high_fallacies,
            medium_fallacies,
        )

    # Check citation grounding
    weak_citations = _identify_weak_citations(answer, citations)
    critique.weak_citations = weak_citations

    if weak_citations:
        LOGGER.info(
            "Flagged %s weak citations: %s",
            len(weak_citations),
            ", ".join(weak_citations),
        )

    # Check for perspective bias
    bias_warnings = _detect_bias(reasoning_trace, answer)
    critique.bias_warnings = bias_warnings

    if bias_warnings:
        LOGGER.info("Bias warnings raised: %s", "; ".join(bias_warnings))

    # Surface alternative interpretations explicitly mentioned in the reasoning
    critique.alternative_interpretations = _extract_alternative_interpretations(
        reasoning_trace, answer
    )

    total_penalty = _calculate_total_penalty(
        high_fallacies=high_fallacies,
        medium_fallacies=medium_fallacies,
        weak_citations=len(weak_citations),
        bias_warnings=len(bias_warnings),
    )

    adjusted_quality = DEFAULT_QUALITY_SCORE - total_penalty
    critique.reasoning_quality = int(
        max(MIN_QUALITY_SCORE, min(adjusted_quality, MAX_QUALITY_SCORE))
    )

    LOGGER.info(
        "Reasoning quality adjusted from %s to %s (penalty=%s)",
        DEFAULT_QUALITY_SCORE,
        critique.reasoning_quality,
        total_penalty,
    )

    # Generate recommendations
    critique.recommendations = _generate_recommendations(critique)

    return critique


def _calculate_total_penalty(
    *,
    high_fallacies: int,
    medium_fallacies: int,
    weak_citations: int,
    bias_warnings: int,
) -> int:
    """Compute the cumulative quality penalty in a single pass."""

    penalties = {
        "high_fallacies": high_fallacies * HIGH_FALLACY_PENALTY,
        "medium_fallacies": medium_fallacies * MEDIUM_FALLACY_PENALTY,
        "weak_citations": weak_citations * WEAK_CITATION_PENALTY,
        "bias_warnings": bias_warnings * BIAS_WARNING_PENALTY,
    }

    total_penalty = sum(penalties.values())

    if total_penalty:
        LOGGER.debug("Penalty breakdown: %s", penalties)

    return total_penalty


def _identify_weak_citations(answer: str, citations: list[dict]) -> list[str]:
    """Identify citations weakly connected to claims using proximity heuristics."""

    if not citations or not answer.strip():
        return []

    validated = [_validate_citation(citation) for citation in citations]
    usable_citations = [citation for citation in validated if citation]

    if not usable_citations:
        return []

    answer_lower = answer.lower()
    weak: list[str] = []

    for citation in usable_citations:
        assert citation is not None
        marker = f"[{citation.index}]"
        marker_lower = marker.lower()

        if marker_lower not in answer_lower:
            LOGGER.debug(
                "Citation [%s] (%s) not referenced in answer",
                citation.index,
                citation.passage_id,
            )
            weak.append(citation.passage_id)
            continue

        if _snippet_supported(answer_lower, marker_lower, citation.snippet):
            continue

        LOGGER.debug(
            "Citation [%s] (%s) flagged as weak due to low contextual overlap",
            citation.index,
            citation.passage_id,
        )
        weak.append(citation.passage_id)

    return [value for value in weak if value]


def _validate_citation(citation: dict | None) -> CitationRecord | None:
    """Validate and normalise citation dictionaries."""

    if not citation or not isinstance(citation, dict):
        LOGGER.warning("Encountered non-dict citation: %s", citation)
        return None

    index = citation.get("index")
    if not isinstance(index, int) or index < 1:
        LOGGER.warning("Skipping citation with invalid index: %s", citation)
        return None

    snippet = (citation.get("snippet") or "").strip()
    if not snippet:
        LOGGER.warning("Skipping citation [%s] due to missing snippet", index)
        return None

    passage_id_candidates = [
        citation.get("passage_id"),
        citation.get("document_id"),
        citation.get("osis"),
        str(index),
    ]
    passage_id = next((value for value in passage_id_candidates if value), "")

    return CitationRecord(
        index=index,
        passage_id=str(passage_id),
        snippet=snippet,
        raw=citation,
    )


def _snippet_supported(answer_lower: str, marker: str, snippet: str) -> bool:
    """Check whether a snippet is explained near its citation marker."""

    snippet_clean = re.sub(r"\s+", " ", snippet.lower()).strip()
    if snippet_clean and snippet_clean in answer_lower:
        return True

    keywords = _extract_snippet_keywords(snippet)
    if not keywords:
        return False

    context = _extract_context_window(answer_lower, marker)
    if not context:
        return False

    if "sources:" in context.lower():
        return True

    context_tokens = set(re.findall(r"[a-z0-9']+", context))
    overlap = keywords & context_tokens
    overlap_ratio = len(overlap) / max(len(keywords), 1)

    if overlap_ratio >= 0.4 or len(overlap) >= MIN_SNIPPET_KEYWORDS:
        return True

    explanatory_markers = {
        "explains",
        "shows",
        "demonstrates",
        "supports",
        "argues",
        "echoes",
        "cites",
        "quotes",
        "references",
        "refers",
    }
    if any(marker in context_tokens for marker in explanatory_markers):
        return True

    if overlap and any(marker in context_tokens for marker in {"clarifies", "connects", "relates"}):
        return True

    return False


def _extract_context_window(answer_lower: str, marker: str) -> str:
    """Return a slice of the answer around the citation marker."""

    position = answer_lower.find(marker)
    if position == -1:
        return ""

    start = max(0, position - CITATION_CONTEXT_WINDOW_CHARS)
    end = min(len(answer_lower), position + len(marker) + CITATION_CONTEXT_WINDOW_CHARS)
    return answer_lower[start:end]


def _extract_snippet_keywords(snippet: str) -> set[str]:
    """Extract informative keywords from a citation snippet."""

    cleaned = re.sub(r"[^a-z0-9\s]", " ", snippet.lower())
    words = [word for word in cleaned.split() if len(word) > 3 and word not in _STOPWORDS]
    if len(words) < MIN_SNIPPET_KEYWORDS:
        return set(words)

    return set(words)


def _detect_bias(reasoning_trace: str, answer: str) -> list[str]:
    """Detect perspective bias in reasoning with context-aware heuristics."""

    combined_text = f"{reasoning_trace}\n{answer}".strip()
    if not combined_text:
        return []

    sentences = [
        sentence.strip()
        for sentence in re.split(r"[.!?]+", combined_text)
        if sentence and sentence.strip()
    ]

    if not sentences:
        return []

    bias_counts = Counter({"apologetic": 0, "skeptical": 0})

    for sentence in sentences:
        lowered = sentence.lower()
        bias_counts["apologetic"] += _count_bias_markers(lowered, APOLOGETIC_MARKERS)
        bias_counts["skeptical"] += _count_bias_markers(lowered, SKEPTICAL_MARKERS)

    total_markers = bias_counts["apologetic"] + bias_counts["skeptical"]
    warnings: list[str] = []

    if bias_counts["apologetic"] >= 2 and not bias_counts["skeptical"]:
        ratio = bias_counts["apologetic"] / max(1, total_markers)
        if ratio >= BIAS_DOMINANCE_RATIO:
            warnings.append(
                "Reasoning leans heavily toward apologetic framing; acknowledge critical scholarship."
            )

    if bias_counts["skeptical"] >= 2 and not bias_counts["apologetic"]:
        ratio = bias_counts["skeptical"] / max(1, total_markers)
        if ratio >= BIAS_DOMINANCE_RATIO:
            warnings.append(
                "Reasoning emphasizes skeptical objections; consider constructive theological readings."
            )

    overconfident_matches = [
        match
        for match in re.finditer(r"\b(obviously|clearly|certainly|undeniably)\b", combined_text, re.IGNORECASE)
        if not _is_negated(combined_text.lower(), match.start())
    ]

    if overconfident_matches:
        warnings.append("Overconfident language detected – supply supporting evidence or soften claims.")

    return warnings


def _count_bias_markers(sentence: str, markers: set[str]) -> int:
    count = 0
    for marker in markers:
        pattern = re.compile(rf"\b{re.escape(marker)}\b")
        for match in pattern.finditer(sentence):
            if not _is_negated(sentence, match.start()):
                count += 1
    return count


def _is_negated(text: str, position: int) -> bool:
    window_start = max(0, position - 25)
    window = text[window_start:position]
    return any(
        re.search(rf"\b{negation}\b", window)
        for negation in NEGATION_WORDS
    )


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

        stripped = _strip_list_prefix(cleaned_line)
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
        re.compile(
            r"\bsome\s+(?:scholars|commentators|interpreters|traditions|theologians|readers)\s+"
            r"(?:argue|interpret|understand|see|suggest|hold)\s+(?P<clause>[^.?!\n]+)",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:while\s+)?others\s+(?:argue|interpret|understand|see|suggest|contend|hold)\s+"
            r"(?P<clause>[^.?!\n]+)",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bcritics\s+(?:argue|contend|suggest|claim)\s+(?P<clause>[^.?!\n]+)",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bone\s+(?:view|reading)\s+(?:is|holds)\s+that\s+(?P<clause>[^.?!\n]+)",
            re.IGNORECASE,
        ),
        re.compile(
            r"\banother\s+(?:view|reading)\s+(?:is|holds)\s+that\s+(?P<clause>[^.?!\n]+)",
            re.IGNORECASE,
        ),
    ]

    for pattern in inline_patterns:
        for match in pattern.finditer(combined_text):
            clause = match.group("clause")
            _add_candidate(clause)

    return interpretations


def _strip_list_prefix(text: str) -> str:
    """Remove common bullet/number prefixes from a line."""

    stripped = text.lstrip()
    stripped = re.sub(r"^[\-\u2022\*\+]+\s*", "", stripped)
    stripped = re.sub(r"^\(?\d{1,2}\)?[.)-]\s*", "", stripped)
    stripped = re.sub(r"^\([a-zA-Z0-9]+\)\s*", "", stripped)
    stripped = re.sub(r"^\d{1,2}\s+", "", stripped)
    stripped = re.sub(r"^\(?[a-zA-Z]\)?[.)-]\s*", "", stripped)
    return stripped.strip()


def _normalise_interpretation_text(text: str) -> str:
    """Normalise extracted interpretation snippets for presentation."""

    cleaned = text.strip().lstrip("-•:;").strip()
    if not cleaned:
        return ""

    cleaned = re.sub(r"^it['’']s\s+", "is ", cleaned, flags=re.IGNORECASE)
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
    cleaned = re.sub(
        r"^(?:may|might|could|would|should|perhaps|possibly)\s+",
        "",
        cleaned,
        count=1,
        flags=re.IGNORECASE,
    )

    trailing_patterns = [
        re.compile(r"(?:,?\s+(?:while|but)\s+others\b.*)$", re.IGNORECASE),
        re.compile(r"(?:,?\s+(?:while|but)\s+some\b.*)$", re.IGNORECASE),
        re.compile(r"(?:,?\s+however\b.*)$", re.IGNORECASE),
    ]
    for pattern in trailing_patterns:
        cleaned = pattern.sub("", cleaned)

    cleaned = re.split(r"[.?!](?:\s|$)", cleaned, maxsplit=1)[0]

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

        Revise the answer to resolve the issues above. Provide enough detail to address
        each critique point, aiming for two or three focused paragraphs, and end with a
        "Sources:" line retaining the citation indices.

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
    remaining_chars = MAX_CITATION_SECTION_CHARS

    for citation in citations[:MAX_CITATIONS_IN_PROMPT]:
        index = citation.get("index")
        snippet = scrub_adversarial_language(
            (citation.get("snippet") or "").strip()
        ) or ""
        snippet = snippet[:200] + ("…" if len(snippet) > 200 else "")
        osis = (
            citation.get("osis")
            or citation.get("document_title")
            or citation.get("document_id")
            or "?"
        )
        anchor = citation.get("anchor") or "context"
        line = f"[{index}] {osis} ({anchor}) — {snippet}"

        if remaining_chars - len(line) <= 0:
            LOGGER.debug("Truncating citation section to stay within token budget")
            break

        lines.append(line)
        remaining_chars -= len(line) + 1

    return "\n".join(lines) if lines else "- None provided."


def _select_revision_citations(
    original_answer: str, critique: Critique, citations: list[dict]
) -> list[dict]:
    """Prioritise citations that are referenced or need strengthening."""

    if not citations:
        return []

    referenced_indices = _extract_referenced_indices(original_answer)
    weak_passage_ids = [pid for pid in critique.weak_citations if pid]

    annotated = [(citation, _validate_citation(citation)) for citation in citations]
    valid_citations = [(citation, record) for citation, record in annotated if record]

    if not valid_citations:
        return []

    selected: list[dict] = []
    seen_ids: set[int] = set()

    for citation, record in valid_citations:
        if record.passage_id in weak_passage_ids and id(citation) not in seen_ids:
            selected.append(citation)
            seen_ids.add(id(citation))

    for index in referenced_indices:
        for citation, record in valid_citations:
            if record.index != index or id(citation) in seen_ids:
                continue
            selected.append(citation)
            seen_ids.add(id(citation))
            break

    for citation, _record in valid_citations:
        if id(citation) in seen_ids:
            continue
        selected.append(citation)
        seen_ids.add(id(citation))
        if len(selected) >= MAX_CITATIONS_IN_PROMPT:
            break

    return selected[:MAX_CITATIONS_IN_PROMPT]


def _extract_referenced_indices(answer: str) -> list[int]:
    matches = re.findall(r"\[(\d+)\]", answer or "")
    seen: set[int] = set()
    ordered: list[int] = []
    for match in matches:
        try:
            value = int(match)
        except ValueError:
            continue
        if value not in seen:
            ordered.append(value)
            seen.add(value)
    return ordered


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
