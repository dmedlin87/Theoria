"""Logical fallacy detection for theological reasoning."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Pattern


@dataclass(slots=True)
class FallacyWarning:
    """Represents a detected logical fallacy."""

    fallacy_type: str
    severity: str  # "low" | "medium" | "high"
    description: str
    matched_text: str
    suggestion: str | None = None


class FallacyDetector:
    """Detects logical fallacies in theological arguments."""

    # Formal fallacies
    AFFIRMING_CONSEQUENT = re.compile(
        r"\b(?:if|when)\s+\w+.*then\s+\w+.*(?:therefore|thus|so)\s+\w+",
        re.IGNORECASE,
    )

    # Informal fallacies
    AD_HOMINEM = re.compile(
        r"\b(?:he|she|they|author|scholar|critic(?:s)?|skeptic(?:s)?|opponent(?:s)?)\s+"
        r"(?:is|are|was)\s+(?:biased|liberal|conservative|unqualified|ignorant)",
        re.IGNORECASE,
    )

    APPEAL_TO_AUTHORITY = re.compile(
        r"\b(?:famous|renowned|expert|scholar|professor)(?:\s+\w+){1,3}\s+"
        r"(?:says|claims|argues|teaches)\s+(?:that|this)",
        re.IGNORECASE,
    )

    CIRCULAR_REASONING = re.compile(
        r"\b(?:because|since)\s+(?:the\s+)?(?:bible|scripture|text)\s+(?:says|teaches|is\s+true)",
        re.IGNORECASE,
    )

    STRAW_MAN = re.compile(
        r"\b(?:critics|skeptics|opponents)\s+(?:claim|say|argue)\s+(?:that|the)\s+\w+\s+(?:is|are)\s+(?:false|wrong|absurd)",
        re.IGNORECASE,
    )

    FALSE_DICHOTOMY = re.compile(
        r"\b(?:either|must\s+be)\s+\w+\s+(?:or|otherwise)\s+\w+",
        re.IGNORECASE,
    )

    # Theological-specific fallacies
    PROOF_TEXTING = re.compile(
        r"(?:[A-Z][a-z]+\.?\s*\d+(?::\d+|\.\d+))(?:\s*,\s*[A-Z][a-z]+\.?\s*\d+(?::\d+|\.\d+)){4,}",
    )

    VERSE_ISOLATION = re.compile(
        r"\b(?:verse|passage)\s+(?:clearly|obviously|plainly)\s+(?:says|teaches|means)",
        re.IGNORECASE,
    )

    EISEGESIS_MARKERS = re.compile(
        r"\b(?:must\s+have\s+meant|really\s+means|actually\s+refers\s+to)\b",
        re.IGNORECASE,
    )

    CHRONOLOGICAL_SNOBBERY = re.compile(
        r"\b(?:ancient|primitive|outdated|modern)\s+(?:view|understanding|knowledge)",
        re.IGNORECASE,
    )

    # Composition patterns
    FALLACY_PATTERNS: list[tuple[Pattern[str], str, str, str]] = [
        (
            AFFIRMING_CONSEQUENT,
            "affirming_consequent",
            "medium",
            "Treats 'if P then Q' and Q as proof of P",
        ),
        (AD_HOMINEM, "ad_hominem", "high", "Attack on person rather than argument"),
        (
            APPEAL_TO_AUTHORITY,
            "appeal_to_authority",
            "medium",
            "Argument relies on authority without warrant",
        ),
        (
            CIRCULAR_REASONING,
            "circular_reasoning",
            "high",
            "Conclusion assumed in premises",
        ),
        (
            STRAW_MAN,
            "straw_man",
            "high",
            "Misrepresenting opponent's position",
        ),
        (
            FALSE_DICHOTOMY,
            "false_dichotomy",
            "medium",
            "Presents false either/or choice",
        ),
        (
            PROOF_TEXTING,
            "proof_texting",
            "high",
            "Rapid-fire citations without context",
        ),
        (
            VERSE_ISOLATION,
            "verse_isolation",
            "medium",
            "Treating verse out of literary context",
        ),
        (
            EISEGESIS_MARKERS,
            "eisegesis",
            "medium",
            "Reading meaning into text rather than from it",
        ),
        (
            CHRONOLOGICAL_SNOBBERY,
            "chronological_snobbery",
            "low",
            "Dismissing ideas based on era",
        ),
    ]

    def detect(self, text: str) -> list[FallacyWarning]:
        """Detect fallacies in the given text."""
        warnings: list[FallacyWarning] = []

        for pattern, fallacy_type, severity, description in self.FALLACY_PATTERNS:
            matches = pattern.finditer(text)
            for match in matches:
                matched_text = match.group(0)
                suggestion = self._get_suggestion(fallacy_type)

                warnings.append(
                    FallacyWarning(
                        fallacy_type=fallacy_type,
                        severity=severity,
                        description=description,
                        matched_text=matched_text,
                        suggestion=suggestion,
                    )
                )

        return warnings

    def _get_suggestion(self, fallacy_type: str) -> str | None:
        """Get remediation suggestion for a fallacy type."""
        suggestions = {
            "affirming_consequent": "Check whether the consequent could hold without the proposed cause.",
            "ad_hominem": "Focus on evaluating the argument's logic, not the person's character.",
            "appeal_to_authority": "Provide the underlying reasoning or evidence, not just the authority's name.",
            "circular_reasoning": "Establish premises independently before drawing conclusions.",
            "straw_man": "Represent the opposing view accurately before critiquing it.",
            "false_dichotomy": "Consider whether additional options exist beyond the two presented.",
            "proof_texting": "Engage with each passage's context rather than listing citations.",
            "verse_isolation": "Consider the surrounding literary context and genre.",
            "eisegesis": "Focus on what the text says before inferring what it means.",
            "chronological_snobbery": "Evaluate ideas on their merits, not their historical era.",
        }
        return suggestions.get(fallacy_type)


# Module-level convenience function
def detect_fallacies(text: str) -> list[FallacyWarning]:
    """Detect logical fallacies in text.

    Args:
        text: The text to analyze for fallacies

    Returns:
        List of detected fallacy warnings
    """
    detector = FallacyDetector()
    return detector.detect(text)
