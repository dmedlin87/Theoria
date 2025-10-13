"""Chain-of-thought reasoning scaffolding for theological AI agents."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from ...models.search import HybridSearchResult
from ..rag.models import RAGCitation


@dataclass(slots=True)
class ReasoningStep:
    """A single step in a chain-of-thought reasoning process."""

    step_number: int
    step_type: str  # "understand" | "identify" | "survey" | "detect" | "weigh" | "check" | "synthesize"
    content: str
    confidence: float | None = None  # 0.0 - 1.0


@dataclass(slots=True)
class ChainOfThought:
    """Parsed chain-of-thought reasoning from model output."""

    steps: list[ReasoningStep]
    raw_thinking: str


def build_cot_prompt(
    question: str,
    citations: Sequence[RAGCitation],
    mode: str = "detective",
    contradictions: list[dict] | None = None,
) -> str:
    """Build a chain-of-thought prompt for theological reasoning.

    Args:
        question: The theological question to reason about
        citations: Retrieved passage citations
        mode: Reasoning mode (detective, critic, apologist, synthesizer)
        contradictions: Optional list of known contradictions to consider

    Returns:
        Formatted prompt with chain-of-thought scaffolding
    """
    mode_prompts = {
        "detective": _build_detective_prompt,
        "critic": _build_critic_prompt,
        "apologist": _build_apologist_prompt,
        "synthesizer": _build_synthesizer_prompt,
    }

    builder = mode_prompts.get(mode, _build_detective_prompt)
    return builder(question, citations, contradictions)


def _build_detective_prompt(
    question: str,
    citations: Sequence[RAGCitation],
    contradictions: list[dict] | None = None,
) -> str:
    """Build prompt for detective mode."""
    passages_text = "\n".join(
        f"[{c.index}] {c.snippet} (OSIS {c.osis}, {c.anchor})" for c in citations
    )

    contradictions_text = ""
    if contradictions:
        contradictions_text = "\n\nKnown Tensions:\n"
        for contra in contradictions[:5]:  # Limit to top 5
            contradictions_text += f"- {contra.get('summary', 'Tension detected')} "
            contradictions_text += f"({contra.get('osis_a', '')} vs {contra.get('osis_b', '')})\n"
            contradictions_text += f"  Perspective: {contra.get('perspective', 'neutral')}\n"

    return f"""You are a theological detective investigating this question. Think step-by-step and show your reasoning.

**Investigation Question:** {question}

**Evidence (Retrieved Passages):**
{passages_text}
{contradictions_text}

**Detective Method:**
1. **Understand the Question:** Rephrase in your own words. What exactly is being asked?
2. **Identify Key Concepts:** List theological terms, frameworks, or background knowledge needed.
3. **Survey Evidence:** Examine each passage. What does it support? What does it challenge?
4. **Detect Tensions:** Flag apparent contradictions or competing interpretations.
5. **Weigh Perspectives:** Consider skeptical, apologetic, and neutral readings of the evidence.
6. **Check Reasoning:** Scan your logic for fallacies (circular reasoning, proof-texting, etc.).
7. **Synthesize:** Form a conclusion with explicit warrant chains linking claims to evidence.
8. **Cite Sources:** Link every claim to specific passages using [index] format.

**Format your reasoning inside <thinking> tags, then provide your answer.**

<thinking>
[Step-by-step reasoning here]
</thinking>

[Your final answer here, 2-3 paragraphs]

Sources: [List all citations in format: [1] Osis.Ref (anchor); [2] Osis.Ref (anchor); ...]
"""


def _build_critic_prompt(
    question: str,
    citations: Sequence[RAGCitation],
    contradictions: list[dict] | None = None,
) -> str:
    """Build prompt for critic mode."""
    passages_text = "\n".join(
        f"[{c.index}] {c.snippet} (OSIS {c.osis}, {c.anchor})" for c in citations
    )

    return f"""You are a skeptical peer reviewer examining this theological claim. Your job is to poke holes and demand rigor.

**Claim Under Review:** {question}

**Available Evidence:**
{passages_text}

**Critical Method:**
1. **Question Every Claim:** Don't accept assertions at face value. What's the warrant?
2. **Demand Stronger Evidence:** Is the citation actually relevant? Is it being read in context?
3. **Surface Alternatives:** What competing interpretations exist? Are they being ignored?
4. **Check Logic:** Identify circular reasoning, appeals to authority, straw men, false dichotomies.
5. **Test Coherence:** Do the cited passages actually support the conclusion, or is this eisegesis?
6. **Rate Strength:** Score the argument from F (fallacious) to A+ (airtight).

<thinking>
[Critical analysis here]
</thinking>

[Your critique, highlighting weaknesses and alternative readings]

Sources: [Citations]
"""


def _build_apologist_prompt(
    question: str,
    citations: Sequence[RAGCitation],
    contradictions: list[dict] | None = None,
) -> str:
    """Build prompt for apologist mode."""
    passages_text = "\n".join(
        f"[{c.index}] {c.snippet} (OSIS {c.osis}, {c.anchor})" for c in citations
    )

    contradictions_text = ""
    if contradictions:
        contradictions_text = "\n\nTensions to Address:\n"
        for contra in contradictions[:5]:
            contradictions_text += f"- {contra.get('summary', '')}\n"

    return f"""You are seeking coherence and harmony in the theological evidence. Build the strongest case for consistency.

**Question:** {question}

**Evidence:**
{passages_text}
{contradictions_text}

**Harmonization Method:**
1. **Find Complementarity:** How might these passages complement rather than contradict?
2. **Surface Context:** What background (genre, audience, purpose) resolves apparent tensions?
3. **Check Translation:** Could Hebrew/Greek nuances clarify ambiguities?
4. **Build Coherence:** Construct the most charitable, internally consistent reading.
5. **Acknowledge Limits:** Note where tensions remain despite harmonization attempts.

<thinking>
[Harmonization reasoning here]
</thinking>

[Your harmonized synthesis]

Sources: [Citations]
"""


def _build_synthesizer_prompt(
    question: str,
    citations: Sequence[RAGCitation],
    contradictions: list[dict] | None = None,
) -> str:
    """Build prompt for neutral synthesizer mode."""
    passages_text = "\n".join(
        f"[{c.index}] {c.snippet} (OSIS {c.osis}, {c.anchor})" for c in citations
    )

    return f"""You are a neutral academic surveying the scholarly landscape. Present the full spectrum fairly.

**Research Question:** {question}

**Source Material:**
{passages_text}

**Synthesis Method:**
1. **Map Positions:** Identify the range of scholarly stances (skeptical, moderate, conservative).
2. **Trace Development:** How has the view evolved historically? Ancient → Patristic → Medieval → Modern?
3. **Consensus vs Dispute:** What's agreed upon? What remains contested?
4. **Evaluate Evidence:** Which positions have stronger textual support? Weaker?
5. **State of the Question:** Summarize current scholarly consensus and open questions.

<thinking>
[Synthetic analysis here]
</thinking>

[Your balanced survey of positions]

Sources: [Citations]
"""


def parse_chain_of_thought(completion: str) -> ChainOfThought:
    """Parse chain-of-thought reasoning from model completion.

    Extracts <thinking> tags and structures into reasoning steps.

    Args:
        completion: The model's generated text

    Returns:
        Parsed chain-of-thought with structured steps
    """
    # Extract thinking section
    thinking_match = re.search(
        r"<thinking>(.*?)</thinking>", completion, re.DOTALL | re.IGNORECASE
    )

    if not thinking_match:
        return ChainOfThought(steps=[], raw_thinking="")

    raw_thinking = thinking_match.group(1).strip()

    # Parse numbered steps
    step_pattern = re.compile(r"^\s*(\d+)\.\s*\*\*([^:*]+):\*\*\s*(.+)$", re.MULTILINE)
    steps: list[ReasoningStep] = []

    for match in step_pattern.finditer(raw_thinking):
        step_num = int(match.group(1))
        step_type = match.group(2).strip().lower()
        content = match.group(3).strip()

        # Map step names to types
        type_mapping = {
            "understand": "understand",
            "identify": "identify",
            "survey": "survey",
            "detect": "detect",
            "weigh": "weigh",
            "check": "check",
            "synthesize": "synthesize",
            "question": "critique",
            "find": "harmonize",
            "map": "survey",
        }

        normalized_type = "reasoning"
        for key, value in type_mapping.items():
            if key in step_type:
                normalized_type = value
                break

        steps.append(
            ReasoningStep(
                step_number=step_num,
                step_type=normalized_type,
                content=content,
            )
        )

    return ChainOfThought(steps=steps, raw_thinking=raw_thinking)
