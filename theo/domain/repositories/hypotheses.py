"""Repository contract for hypotheses persistence."""

from typing import Mapping, Protocol

from ..research import Hypothesis, HypothesisDraft


class HypothesisRepository(Protocol):
    """Persistence operations for hypotheses."""

    def create(self, draft: HypothesisDraft, *, commit: bool = True) -> Hypothesis:
        """Persist a hypothesis and return the stored aggregate."""

    def list(
        self,
        *,
        statuses: tuple[str, ...] | None = None,
        min_confidence: float | None = None,
        query: str | None = None,
    ) -> list[Hypothesis]:
        """Return hypotheses matching the provided filters."""

    def update(self, hypothesis_id: str, changes: Mapping[str, object]) -> Hypothesis:
        """Apply updates and return the refreshed aggregate."""


__all__ = ["HypothesisRepository"]
