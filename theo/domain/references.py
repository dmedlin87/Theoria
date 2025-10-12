"""Value objects describing OSIS-aligned scripture references."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScriptureReference:
    """Canonical OSIS-formatted verse reference."""

    osis_id: str
    start_verse: int | None = None
    end_verse: int | None = None

    def __post_init__(self) -> None:  # pragma: no cover - defensive check
        if not self.osis_id:
            raise ValueError("osis_id must be non-empty")

    def to_range(self) -> str:
        """Return a human-friendly representation of the verse range."""

        if self.start_verse is None and self.end_verse is None:
            return self.osis_id
        if self.start_verse == self.end_verse:
            return f"{self.osis_id}.{self.start_verse}"
        start = f"{self.start_verse}" if self.start_verse is not None else "?"
        end = f"{self.end_verse}" if self.end_verse is not None else "?"
        return f"{self.osis_id}.{start}-{end}"
