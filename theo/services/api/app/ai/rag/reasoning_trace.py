"""Utilities for constructing structured reasoning traces."""

from __future__ import annotations

import re

from ..reasoning.chain_of_thought import parse_chain_of_thought
from .models import ReasoningTrace, ReasoningTraceStep

_STEP_LABELS = {
    "understand": "Understand the question",
    "identify": "Identify key concepts",
    "survey": "Survey the evidence",
    "detect": "Detect tensions",
    "weigh": "Weigh perspectives",
    "check": "Check reasoning",
    "synthesize": "Synthesize conclusion",
    "critique": "Critique argument",
    "harmonize": "Harmonize insights",
}

_MODE_STRATEGIES = {
    "detective": "Detective reasoning",
    "critic": "Critical review",
    "apologist": "Apologetic synthesis",
    "synthesizer": "Scholarly synthesis",
}

_CITATION_PATTERN = re.compile(r"\[(\d+)]")


def build_reasoning_trace_from_completion(
    completion: str | None,
    *,
    mode: str | None = None,
) -> ReasoningTrace | None:
    """Parse a model completion into a structured reasoning trace.

    Parameters
    ----------
    completion:
        Full model response including any ``<thinking>`` scaffolding.
    mode:
        Optional chat mode used to annotate the reasoning strategy.

    Returns
    -------
    ReasoningTrace | None
        Structured reasoning trace if reasoning content was detected, otherwise ``None``.
    """

    if not completion:
        return None

    chain = parse_chain_of_thought(completion)
    if not chain.steps:
        return None

    steps: list[ReasoningTraceStep] = []
    for step in chain.steps:
        detail = step.content.strip()
        if not detail:
            continue

        citations = _extract_citations(detail)
        label = _STEP_LABELS.get(step.step_type.lower(), _format_step_label(step.step_type))

        steps.append(
            ReasoningTraceStep(
                id=f"step-{step.step_number}",
                label=label,
                detail=detail,
                citations=citations,
                confidence=step.confidence,
            )
        )

    if not steps:
        return None

    summary = steps[0].detail if isinstance(steps[0].detail, str) else None
    if summary and len(summary) > 280:
        summary = summary[:277].rstrip() + "..."
    strategy = _format_strategy(mode)

    return ReasoningTrace(summary=summary, strategy=strategy, steps=steps)


def _extract_citations(detail: str) -> list[int]:
    """
    Extract citation indices from a reasoning step detail string.

    Assumes citations in the model output are 1-based (e.g., [1], [2], ...).
    If citations are not 1-based, this function may produce incorrect indices.
    Only positive citation numbers are considered valid.
    """
    unique_indices: set[int] = set()
    for match in _CITATION_PATTERN.finditer(detail):
        try:
            raw_number = int(match.group(1))
        except ValueError:
            continue
        if raw_number < 1:
            # Invalid citation number; skip and optionally log or warn
            continue
        citation_index = raw_number - 1
        unique_indices.add(citation_index)
    return sorted(unique_indices)


def _format_step_label(step_type: str) -> str:
    normalized = step_type.strip() if step_type else ""
    if not normalized:
        return "Reasoning step"
    words = normalized.replace("_", " ").split()
    return " ".join(word.capitalize() for word in words)


def _format_strategy(mode: str | None) -> str | None:
    if not mode:
        return None
    key = mode.strip().lower()
    if not key:
        return None
    return _MODE_STRATEGIES.get(key, _format_step_label(key))


__all__ = ["build_reasoning_trace_from_completion"]
