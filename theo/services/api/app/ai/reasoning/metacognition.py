"""Meta-cognitive reflection and self-critique capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import textwrap
from typing import Iterable

from ..clients import LanguageModelClient
from ..rag.guardrail_helpers import scrub_adversarial_language
from .fallacies import FallacyWarning, detect_fallacies


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
    critique = Critique(reasoning_quality=70)  # Default mid-range

    # Detect logical fallacies
    fallacies = detect_fallacies(reasoning_trace + " " + answer)
    critique.fallacies_found = fallacies

    # Penalize quality for fallacies
    fallacy_penalty = len([f for f in fallacies if f.severity == "high"]) * 15
    fallacy_penalty += len([f for f in fallacies if f.severity == "medium"]) * 8
    critique.reasoning_quality = max(0, critique.reasoning_quality - fallacy_penalty)

    # Check citation grounding
    weak_citations = _identify_weak_citations(answer, citations)
    critique.weak_citations = weak_citations

    if weak_citations:
        critique.reasoning_quality -= len(weak_citations) * 5

    # Check for perspective bias
    bias_warnings = _detect_bias(reasoning_trace, answer)
    critique.bias_warnings = bias_warnings

    if bias_warnings:
        critique.reasoning_quality -= len(bias_warnings) * 10

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

    # Simple heuristic: if citation is mentioned but snippet doesn't appear, it's weak
    answer_lower = answer.lower()

    for citation in citations:
        index = citation.get("index", 0)
        snippet = citation.get("snippet", "")

        citation_mentioned = f"[{index}]" in answer

        cleaned_snippet = re.sub(r"[^a-z0-9\s]", " ", snippet.lower())
        snippet_words = {
            word
            for word in cleaned_snippet.split()[:10]
            if len(word) > 3 and word not in _STOPWORDS
        }
        snippet_overlap = any(word in answer_lower for word in snippet_words)

        if citation_mentioned and not snippet_overlap:
            weak.append(citation.get("passage_id", ""))

    return weak


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

    # Check for apologetic bias markers
    apologetic_markers = [
        "harmony",
        "harmonious",
        "coherent",
        "consistent",
        "resolves",
        "complements",
        "aligned",
        "seamless",
    ]
    apologetic_count = sum(1 for marker in apologetic_markers if marker in combined_text)

    # Check for skeptical bias markers
    skeptical_markers = [
        "contradiction",
        "inconsistent",
        "incoherent",
        "error",
        "impossible",
        "fabricated",
    ]
    skeptical_count = sum(1 for marker in skeptical_markers if marker in combined_text)

    # If heavily skewed, flag bias
    if apologetic_count >= 3 and skeptical_count <= 1:
        warnings.append("Reasoning shows apologetic bias - consider skeptical objections")

    if skeptical_count >= 4 and apologetic_count <= 1:
        warnings.append("Reasoning shows skeptical bias - consider harmonization attempts")

    # Check for dismissiveness
    if "obviously" in combined_text or "clearly" in combined_text:
        warnings.append("Overconfident language detected - claims may need more support")

    return warnings


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

    fallacies_section = _format_fallacies(critique.fallacies_found)
    weak_citations_section = _format_weak_citations(critique, citations)
    bias_section = _format_simple_list(
        critique.bias_warnings, empty_message="- None detected."
    )
    recommendations_section = _format_simple_list(
        critique.recommendations,
        empty_message="- None provided.",
    )
    citations_section = _format_citations(citations)

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
        return "None provided."
    lines = []
    for citation in citations:
        index = citation.get("index")
        snippet = scrub_adversarial_language(
            (citation.get("snippet") or "").strip()
        ) or ""
        osis = citation.get("osis") or citation.get("document_title") or citation.get("document_id") or "?"
        anchor = citation.get("anchor") or "context"
        lines.append(
            f"[{index}] {osis} ({anchor}) — {snippet}"
        )
    return "\n".join(lines)


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
