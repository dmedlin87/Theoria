"""Reasoning and meta-cognitive capabilities for theological AI agents."""

from .fallacies import FallacyDetector, FallacyWarning, detect_fallacies
from .chain_of_thought import ChainOfThought, ReasoningStep, build_cot_prompt
from .hypotheses import (
    Hypothesis,
    HypothesisGenerator,
    HypothesisTest,
    test_hypothesis,
    update_hypothesis_confidence,
)
from .insights import Insight, InsightDetector, detect_insights
from .metacognition import Critique, RevisionResult, critique_reasoning, revise_with_critique
from .perspectives import PerspectiveSynthesis, synthesize_perspectives

__all__ = [
    "FallacyDetector",
    "FallacyWarning",
    "detect_fallacies",
    "ChainOfThought",
    "ReasoningStep",
    "build_cot_prompt",
    "Hypothesis",
    "HypothesisGenerator",
    "HypothesisTest",
    "test_hypothesis",
    "update_hypothesis_confidence",
    "Insight",
    "InsightDetector",
    "detect_insights",
    "Critique",
    "RevisionResult",
    "critique_reasoning",
    "revise_with_critique",
    "PerspectiveSynthesis",
    "synthesize_perspectives",
]
