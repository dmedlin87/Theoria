"""Logical fallacy detection for theological reasoning."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Iterable, Pattern

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class FallacyWarning:
    """Represents a detected logical fallacy."""

    fallacy_type: str
    severity: str  # "low" | "medium" | "high"
    description: str
    matched_text: str
    suggestion: str | None = None


@dataclass(frozen=True)
class FallacyRule:
    """Definition of a fallacy detection rule."""

    fallacy_type: str
    severity: str
    description: str
    detector: Callable[[str], Iterable[str]]


class FallacyDetector:
    """Detects logical fallacies in theological arguments."""

    AFFIRMING_CONSEQUENT_PATTERN = re.compile(
        r"\bif\s+(?P<antecedent>[^.?!,:;]+?)\s*,?\s*then\s+(?P<consequent>[^.?!]+?)\s*(?:\.|;|,)?\s*(?:therefore|thus|so)\s+(?P<conclusion>[^.?!]+)",
        re.IGNORECASE,
    )

    AD_HOMINEM_PATTERN = re.compile(
        r"\b(?:he|she|they|author|scholar|critic(?:s)?|skeptic(?:s)?|opponent(?:s)?)\s+"
        r"(?:is|are|was)\s+(?:biased|liberal|conservative|unqualified|ignorant)",
        re.IGNORECASE,
    )

    APPEAL_TO_AUTHORITY_PATTERN = re.compile(
        r"\b(?:famous|renowned|expert|scholar|professor)(?:\s+\w+){1,3}\s+"
        r"(?:says|claims|argues|teaches)\s+(?:that|this)",
        re.IGNORECASE,
    )

    CIRCULAR_REASONING_PATTERN = re.compile(
        r"\b(?:because|since)\s+(?:the\s+)?(?:bible|scripture|text)\s+(?:says|teaches|is\s+true)(?P<body>[^.?!]{0,160})(?:therefore|thus|so)\s+(?P<conclusion>[^.?!]+)",
        re.IGNORECASE,
    )

    STRAW_MAN_PATTERN = re.compile(
        r"\b(?:critics|skeptics|opponents)\s+(?:claim|say|argue)\s+(?:that|the)\s+\w+\s+(?:is|are)\s+(?:false|wrong|absurd)",
        re.IGNORECASE,
    )

    FALSE_DICHOTOMY_PATTERN = re.compile(
        r"\beither\s+(?P<option_a>[^.?!,;:]+)\s+or\s+(?P<option_b>[^.?!,;:]+)(?P<tail>[^.?!]{0,80})",
        re.IGNORECASE,
    )

    PROOF_TEXTING_PATTERN = re.compile(
        r"(?:(?:[1-3]?\s?[A-Z][a-z]+\.?\s*)\d+(?:(?::|\.)\d+(?:-\d+)?)?)"
        r"(?:\s*(?:,|;|and)\s*(?:[1-3]?\s?[A-Z][a-z]+\.?\s*\d+(?:(?::|\.)\d+(?:-\d+)?)?)){4,}",
        re.IGNORECASE,
    )

    CITATION_TOKEN_PATTERN = re.compile(
        r"[1-3]?\s?[A-Z][a-z]+\.?\s*\d+(?:(?::|\.)\d+(?:-\d+)?)?",
        re.IGNORECASE,
    )

    VERSE_ISOLATION_PATTERN = re.compile(
        r"\b(?:verse|passage)\s+(?:clearly|obviously|plainly)\s+(?:says|teaches|means)",
        re.IGNORECASE,
    )

    EISEGESIS_PATTERN = re.compile(
        r"\b(?:must\s+have\s+meant|really\s+means|actually\s+refers\s+to)\b",
        re.IGNORECASE,
    )

    CHRONOLOGICAL_SNOBBERY_PATTERN = re.compile(
        r"\b(?:ancient|primitive|outdated|modern)\s+(?:view|understanding|knowledge)",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        self.rules: list[FallacyRule] = [
            FallacyRule(
                "affirming_consequent",
                "medium",
                "Treats 'if P then Q' and Q as proof of P",
                detector=_regex_detector(
                    self.AFFIRMING_CONSEQUENT_PATTERN,
                    _affirming_consequent_filter,
                ),
            ),
            FallacyRule(
                "ad_hominem",
                "high",
                "Attack on person rather than argument",
                detector=_regex_detector(self.AD_HOMINEM_PATTERN),
            ),
            FallacyRule(
                "appeal_to_authority",
                "medium",
                "Argument relies on authority without warrant",
                detector=_regex_detector(self.APPEAL_TO_AUTHORITY_PATTERN),
            ),
            FallacyRule(
                "circular_reasoning",
                "high",
                "Conclusion assumed in premises",
                detector=lambda text: _detect_circular_reasoning(
                    text,
                    self.CIRCULAR_REASONING_PATTERN,
                ),
            ),
            FallacyRule(
                "straw_man",
                "high",
                "Misrepresenting opponent's position",
                detector=_regex_detector(self.STRAW_MAN_PATTERN),
            ),
            FallacyRule(
                "false_dichotomy",
                "medium",
                "Presents false either/or choice",
                detector=_regex_detector(
                    self.FALSE_DICHOTOMY_PATTERN,
                    _false_dichotomy_filter,
                ),
            ),
            FallacyRule(
                "proof_texting",
                "high",
                "Rapid-fire citations without context",
                detector=lambda text: _detect_proof_texting(
                    text,
                    self.PROOF_TEXTING_PATTERN,
                    self.CITATION_TOKEN_PATTERN,
                ),
            ),
            FallacyRule(
                "verse_isolation",
                "medium",
                "Treating verse out of literary context",
                detector=_regex_detector(self.VERSE_ISOLATION_PATTERN),
            ),
            FallacyRule(
                "eisegesis",
                "medium",
                "Reading meaning into text rather than from it",
                detector=_regex_detector(self.EISEGESIS_PATTERN),
            ),
            FallacyRule(
                "chronological_snobbery",
                "low",
                "Dismissing ideas based on era",
                detector=_regex_detector(self.CHRONOLOGICAL_SNOBBERY_PATTERN),
            ),
        ]

    def detect(self, text: str) -> list[FallacyWarning]:
        """Detect fallacies in the given text."""

        grouped: dict[str, list[FallacyWarning]] = defaultdict(list)
        seen_snippets: dict[str, set[str]] = defaultdict(set)
        occurrence_counts: dict[str, int] = defaultdict(int)

        for rule in self.rules:
            for snippet in rule.detector(text):
                normalised = _normalise_snippet(snippet)
                occurrence_counts[rule.fallacy_type] += 1
                if normalised in seen_snippets[rule.fallacy_type]:
                    continue
                seen_snippets[rule.fallacy_type].add(normalised)
                grouped[rule.fallacy_type].append(
                    FallacyWarning(
                        fallacy_type=rule.fallacy_type,
                        severity=rule.severity,
                        description=rule.description,
                        matched_text=snippet.strip(),
                        suggestion=self._get_suggestion(rule.fallacy_type),
                    )
                )

        warnings: list[FallacyWarning] = []
        for fallacy_type, fallacy_warnings in grouped.items():
            primary = fallacy_warnings[0]
            total_instances = occurrence_counts.get(fallacy_type, len(fallacy_warnings))
            if total_instances > 1:
                description = (
                    f"{primary.description} (detected {total_instances} instances)"
                )
                primary = FallacyWarning(
                    fallacy_type=primary.fallacy_type,
                    severity=primary.severity,
                    description=description,
                    matched_text=primary.matched_text,
                    suggestion=primary.suggestion,
                )
            warnings.append(primary)

        if warnings:
            LOGGER.debug(
                "Fallacy warnings issued: %s",
                {warning.fallacy_type: warning.description for warning in warnings},
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


# Helper utilities ---------------------------------------------------------


def _regex_detector(
    pattern: Pattern[str],
    filter_fn: Callable[[re.Match[str], str], bool] | None = None,
) -> Callable[[str], list[str]]:
    def _detect(text: str) -> list[str]:
        matches: list[str] = []
        for match in pattern.finditer(text):
            if filter_fn and not filter_fn(match, text):
                continue
            matches.append(match.group(0))
        return matches

    return _detect


def _affirming_consequent_filter(match: re.Match[str], _: str) -> bool:
    antecedent = match.group("antecedent") or ""
    conclusion = match.group("conclusion") or ""
    if not antecedent or not conclusion:
        return False
    similarity = _jaccard_similarity(antecedent, conclusion)
    return similarity >= 0.4


def _circular_reasoning_filter(match: re.Match[str], _: str) -> bool:
    body = match.group("body") or ""
    conclusion = match.group("conclusion") or ""
    if not conclusion:
        return False
    similarity = _jaccard_similarity(body, conclusion)
    return similarity >= 0.3


def _false_dichotomy_filter(match: re.Match[str], text: str) -> bool:
    tail = (match.group("tail") or "").lower()
    lead_context = text[max(0, match.start() - 60) : match.start()].lower()
    keywords = ("no other", "only", "must", "cannot", "otherwise", "nothing else")
    return any(keyword in tail or keyword in lead_context for keyword in keywords)


def _detect_proof_texting(
    text: str,
    block_pattern: Pattern[str],
    citation_pattern: Pattern[str],
) -> list[str]:
    matches: list[str] = []
    for match in block_pattern.finditer(text):
        snippet = match.group(0)
        citations = citation_pattern.findall(snippet)
        if len(citations) < 5:
            continue
        non_citation = citation_pattern.sub(" ", snippet)
        non_citation_words = [
            token
            for token in re.findall(r"[A-Za-z]+", non_citation)
            if len(token) > 2
        ]
        ratio = len(non_citation_words) / len(citations)
        if ratio <= 0.75:
            context_after = text[match.end() : match.end() + 60]
            explanatory_words = [
                token
                for token in re.findall(r"[A-Za-z]+", context_after)
                if len(token) > 3
            ]
            if len(explanatory_words) >= 2:
                continue
            matches.append(snippet)
    return matches


def _detect_circular_reasoning(
    text: str,
    pattern: Pattern[str],
) -> list[str]:
    matches: list[str] = []
    for match in pattern.finditer(text):
        if _circular_reasoning_filter(match, text):
            matches.append(match.group(0))

    simple_pattern = re.compile(
        r"\b(?P<claim>[A-Za-z\s]+?)\s+because\s+(?:the\s+)?(?:bible|scripture|text)\s+(?:says|teaches)\s+(?P<support>[^.?!]+)",
        re.IGNORECASE,
    )
    for match in simple_pattern.finditer(text):
        claim = match.group("claim") or ""
        support = match.group("support") or ""
        if "says so" in match.group(0).lower():
            matches.append(match.group(0))
            continue
        if _jaccard_similarity(claim, support) >= 0.4:
            matches.append(match.group(0))

    return matches


def _normalise_snippet(snippet: str) -> str:
    return re.sub(r"\s+", " ", snippet.strip().lower())


def _tokenise(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z']+", text.lower()) if len(token) > 3}


def _jaccard_similarity(left: str, right: str) -> float:
    left_tokens = _tokenise(left)
    right_tokens = _tokenise(right)
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = left_tokens & right_tokens
    union = left_tokens | right_tokens
    return len(intersection) / len(union)


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
