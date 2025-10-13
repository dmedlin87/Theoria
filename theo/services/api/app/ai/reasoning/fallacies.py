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
        r"\b(?:if|when)\s+(?P<ante>[^.?!]{3,80})\s+then\s+(?P<cons>[^.?!]{3,80})",
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
        r"\b(?:because|since)\s+(?:the\s+)?(?:bible|scripture|text)\s+(?:says|teaches)",
        re.IGNORECASE,
    )

    STRAW_MAN = re.compile(
        r"\b(?:critics|skeptics|opponents)\s+(?:claim|say|argue)\s+(?:that|the)\s+\w+\s+(?:is|are)\s+(?:false|wrong|absurd)",
        re.IGNORECASE,
    )

    FALSE_DICHOTOMY = re.compile(
        r"\beither\b[^.?!]{3,80}?\bor\b[^.?!]{3,80}",
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
        seen_matches: set[tuple[str, str]] = set()

        for pattern, fallacy_type, severity, description in self.FALLACY_PATTERNS:
            matches = pattern.finditer(text)
            for match in matches:
                if fallacy_type == "circular_reasoning" and not self._is_circular_context(
                    match, text
                ):
                    continue
                if fallacy_type == "proof_texting" and not self._is_proof_texting_context(
                    match, text
                ):
                    continue
                if fallacy_type == "false_dichotomy" and not self._is_false_dichotomy_context(
                    match, text
                ):
                    continue
                if (
                    fallacy_type == "affirming_consequent"
                    and not self._is_affirming_consequent(match, text)
                ):
                    continue

                matched_text = match.group(0)
                key = (fallacy_type, re.sub(r"\s+", " ", matched_text.strip().lower()))
                if key in seen_matches:
                    continue
                seen_matches.add(key)

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

    @staticmethod
    def _extract_sentence(text: str, position: int) -> str:
        start = text.rfind(".", 0, position) + 1
        start = max(start, text.rfind("?", 0, position) + 1, text.rfind("!", 0, position) + 1)
        end_candidates = [
            idx for idx in (text.find(delim, position) for delim in ".?!") if idx != -1
        ]
        end = min(end_candidates) if end_candidates else len(text)
        return text[start:end]

    def _is_circular_context(self, match: re.Match[str], text: str) -> bool:
        sentence = self._extract_sentence(text, match.start())
        trailing_claim = re.search(
            r"(therefore|thus|so)\s+(?:we\s+)?(?:know|conclude|it\s+is)\s+(?:true|reliable|correct)",
            sentence,
            re.IGNORECASE,
        )
        direct_assertion = re.search(
            r"\bis\s+(?:true|reliable|correct)\s+because\s+(?:the\s+)?(?:bible|scripture|text)\s+(?:says|teaches)",
            sentence,
            re.IGNORECASE,
        )
        return bool(trailing_claim or direct_assertion)

    def _is_proof_texting_context(self, match: re.Match[str], text: str) -> bool:
        span = match.group(0)
        non_citation_content = re.sub(
            r"(?:[1-3]?[A-Z][a-z]+\.?\s*\d+(?::\d+|\.\d+)?|\s|,|;|and|or|cf\.)",
            "",
            span,
            flags=re.IGNORECASE,
        )
        if non_citation_content:
            return False

        trailing_context = text[match.end() : match.end() + 120]
        explanatory = re.search(
            r"\b(parallel|context|discussion|explain|explores|summarises|survey)\b",
            trailing_context,
            re.IGNORECASE,
        )
        return explanatory is None

    def _is_false_dichotomy_context(self, match: re.Match[str], text: str) -> bool:
        sentence = self._extract_sentence(text, match.start())
        return bool(
            re.search(
                r"\b(no other|only|must|cannot both|exclusive|one true)\b",
                sentence,
                re.IGNORECASE,
            )
        )

    def _is_affirming_consequent(self, match: re.Match[str], text: str) -> bool:
        antecedent = match.group("ante").strip()
        consequent = match.group("cons").strip()
        remainder = text[match.end() : match.end() + 200]
        if not antecedent or not consequent:
            return False

        consequent_present = re.search(
            rf"\b{re.escape(consequent.strip().split(',')[0])}\b",
            remainder,
            re.IGNORECASE,
        )

        antecedent_fragment = antecedent.strip().split(",")[0][:40].lower()
        conclusion_pattern = re.compile(
            rf"(therefore|thus|so)\s+(?:we\s+)?(?:conclude|know|affirm|it\s+follows)\s+{re.escape(antecedent_fragment)}",
            re.IGNORECASE,
        )

        remainder_lower = remainder.lower()
        return bool(consequent_present and conclusion_pattern.search(remainder_lower))

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
