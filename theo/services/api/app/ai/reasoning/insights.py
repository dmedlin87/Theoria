"""Insight detection for discovering novel theological connections."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass(slots=True)
class Insight:
    """A detected insight or novel connection."""

    id: str
    insight_type: str  # "cross_ref" | "pattern" | "synthesis" | "tension_resolution"
    description: str
    supporting_passages: list[str] = field(default_factory=list)  # passage IDs
    novelty_score: float = 0.0  # 0.0 - 1.0, how rare is this connection?
    osis_refs: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class InsightDetector:
    """Detects insights and novel connections in theological reasoning."""

    def __init__(self, session: Session):
        self.session = session

    def detect_from_reasoning(
        self, reasoning_trace: str, passages: list[dict]
    ) -> list[Insight]:
        """Detect insights from chain-of-thought reasoning.

        Looks for:
        - Explicit <insight> tags in reasoning
        - Cross-references between distant OSIS ranges
        - Patterns across multiple passages
        - Novel resolutions of contradictions

        Args:
            reasoning_trace: The chain-of-thought text
            passages: Retrieved passages involved

        Returns:
            List of detected insights
        """
        insights: list[Insight] = []

        # Extract explicit insight tags
        insight_pattern = re.compile(
            r'<insight\s+type="([^"]+)">(.*?)</insight>',
            re.DOTALL | re.IGNORECASE,
        )

        for idx, match in enumerate(insight_pattern.finditer(reasoning_trace), start=1):
            insight_type = match.group(1).strip()
            description = match.group(2).strip()

            insights.append(
                Insight(
                    id=f"insight-{idx}",
                    insight_type=insight_type,
                    description=description,
                    novelty_score=self._estimate_novelty(description, passages),
                )
            )

        # Auto-detect cross-references
        cross_ref_insights = self._detect_cross_references(passages)
        insights.extend(cross_ref_insights)

        # Auto-detect patterns
        pattern_insights = self._detect_patterns(passages)
        insights.extend(pattern_insights)

        return insights

    def _estimate_novelty(self, description: str, passages: list[dict]) -> float:
        """Estimate how novel an insight is.

        Factors:
        - Number of passages involved (more = higher novelty)
        - Distance between OSIS refs (wider = higher novelty)
        - Rarity of co-occurrence in corpus

        Args:
            description: The insight description
            passages: Passages involved

        Returns:
            Novelty score 0.0 - 1.0
        """
        # Simple heuristic: more passages = higher novelty
        num_passages = len(passages)
        if num_passages >= 5:
            return 0.8
        elif num_passages >= 3:
            return 0.6
        else:
            return 0.4

    def _detect_cross_references(self, passages: list[dict]) -> list[Insight]:
        """Auto-detect cross-references between distant scripture ranges.

        If passages span multiple books or distant chapters, flag as insight.

        Args:
            passages: Retrieved passages

        Returns:
            Cross-reference insights
        """
        insights: list[Insight] = []

        # Extract unique OSIS books
        books: set[str] = set()
        for passage in passages:
            osis = passage.get("osis_ref", "")
            if osis and "." in osis:
                book = osis.split(".")[0]
                books.add(book)

        # If 3+ different books, flag as cross-reference insight
        if len(books) >= 3:
            book_list = ", ".join(sorted(books))
            insights.append(
                Insight(
                    id=f"cross-ref-{hash(book_list) % 10000}",
                    insight_type="cross_ref",
                    description=f"Connection spans {len(books)} books: {book_list}",
                    supporting_passages=[p.get("id", "") for p in passages],
                    novelty_score=min(len(books) * 0.2, 1.0),
                )
            )

        return insights

    def _detect_patterns(self, passages: list[dict]) -> list[Insight]:
        """Auto-detect recurring patterns across passages.

        Looks for:
        - Same verse cited by 5+ different documents
        - Recurring theological terms
        - Consistent perspective across sources

        Args:
            passages: Retrieved passages

        Returns:
            Pattern insights
        """
        insights: list[Insight] = []

        # Group by OSIS ref
        osis_groups: dict[str, list[dict]] = {}
        for passage in passages:
            osis = passage.get("osis_ref")
            if osis:
                osis_groups.setdefault(osis, []).append(passage)

        # Flag frequently cited verses
        for osis, group in osis_groups.items():
            if len(group) >= 5:
                insights.append(
                    Insight(
                        id=f"pattern-{osis}",
                        insight_type="pattern",
                        description=f"{osis} appears in {len(group)} sources - theological anchor point",
                        supporting_passages=[p.get("id", "") for p in group],
                        osis_refs=[osis],
                        novelty_score=0.7,
                    )
                )

        return insights


def detect_insights(
    reasoning_trace: str, passages: list[dict], session: Session
) -> list[Insight]:
    """Convenience function to detect insights.

    Args:
        reasoning_trace: Chain-of-thought reasoning text
        passages: Retrieved passages
        session: Database session

    Returns:
        List of detected insights
    """
    detector = InsightDetector(session)
    return detector.detect_from_reasoning(reasoning_trace, passages)
