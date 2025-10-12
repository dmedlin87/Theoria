"""Meta-cognitive reflection and self-critique capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field

from .fallacies import FallacyWarning, detect_fallacies


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
    for citation in citations:
        index = citation.get("index", 0)
        snippet = citation.get("snippet", "")

        citation_mentioned = f"[{index}]" in answer

        # Extract a few key words from snippet
        snippet_words = set(snippet.lower().split()[:10])
        snippet_overlap = any(word in answer.lower() for word in snippet_words)

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
    apologetic_markers = ["harmony", "coherent", "consistent", "resolves", "complements"]
    apologetic_count = sum(1 for marker in apologetic_markers if marker in combined_text)

    # Check for skeptical bias markers
    skeptical_markers = ["contradiction", "inconsistent", "error", "impossible", "fabricated"]
    skeptical_count = sum(1 for marker in skeptical_markers if marker in combined_text)

    # If heavily skewed, flag bias
    if apologetic_count >= 4 and skeptical_count <= 1:
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
    # In real implementation, would call LLM to revise
) -> RevisionResult:
    """Revise an answer based on critique.
    
    This is a placeholder for LLM-based revision.
    In production, would call LLM with critique as context.
    
    Args:
        original_answer: The original generated answer
        critique: The self-critique
        
    Returns:
        Revision result with improvements
    """
    # TODO: Implement LLM-based revision
    # Would include critique in prompt: "Here's your original answer and critique. Revise to address issues."

    return RevisionResult(
        original_answer=original_answer,
        revised_answer=original_answer,  # Placeholder
        critique_addressed=[],
        improvements="Revision not yet implemented",
        quality_delta=0,
    )
