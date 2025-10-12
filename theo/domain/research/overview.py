"""Helpers for building a reliability overview snapshot for a verse."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .entities import ResearchNote
from .variants import VariantEntry

SUPPORTED_MODES = {"apologetic", "skeptical"}
SUPPORTIVE_STANCES = {"apologetic", "supportive", "harmonizing", "pro"}
CRITICAL_STANCES = {"skeptical", "critical", "contrary", "challenge"}
NEUTRAL_STANCES = {"neutral", "background"}


@dataclass(frozen=True, slots=True)
class OverviewBullet:
    summary: str
    citations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReliabilityOverview:
    osis: str
    mode: str
    consensus: tuple[OverviewBullet, ...]
    disputed: tuple[OverviewBullet, ...]
    manuscripts: tuple[OverviewBullet, ...]


def build_reliability_overview(
    *,
    osis: str,
    notes: Sequence[ResearchNote],
    variants: Sequence[VariantEntry],
    mode: str | None = None,
    note_limit: int = 3,
    manuscript_limit: int = 3,
) -> ReliabilityOverview:
    """Construct a compact overview balancing consensus and disputed claims."""

    normalized_mode = (mode or "apologetic").lower()
    if normalized_mode not in SUPPORTED_MODES:
        normalized_mode = "apologetic"

    supportive: list[OverviewBullet] = []
    critical: list[OverviewBullet] = []
    neutral: list[OverviewBullet] = []

    for note in notes:
        bullet = _note_to_bullet(note)
        if bullet is None:
            continue

        stance = (note.stance or "").strip().lower()
        if stance in SUPPORTIVE_STANCES:
            supportive.append(bullet)
        elif stance in CRITICAL_STANCES:
            critical.append(bullet)
        elif stance in NEUTRAL_STANCES:
            neutral.append(bullet)
        else:
            neutral.append(bullet)

    if normalized_mode == "skeptical":
        consensus = (critical + neutral)[:note_limit]
        disputed = supportive[:note_limit]
    else:
        consensus = (supportive + neutral)[:note_limit]
        disputed = critical[:note_limit]

    manuscripts = _manuscript_bullets(variants, limit=manuscript_limit)

    return ReliabilityOverview(
        osis=osis,
        mode=normalized_mode,
        consensus=tuple(consensus),
        disputed=tuple(disputed),
        manuscripts=tuple(manuscripts),
    )


def _note_to_bullet(note: ResearchNote) -> OverviewBullet | None:
    """Translate a research note into a short, reader-friendly bullet."""

    text_source = (note.title or "").strip() or note.body.strip()
    if not text_source:
        return None

    summary = _first_sentence(text_source)
    citations = _extract_citations(note)
    return OverviewBullet(summary=summary, citations=tuple(citations))


def _first_sentence(text: str) -> str:
    """Return a concise first sentence suitable for a grade-school reading level."""

    cleaned = text.replace("\n", " ").strip()
    if not cleaned:
        return ""

    for delimiter in [". ", "? ", "! "]:
        if delimiter in cleaned:
            sentence = cleaned.split(delimiter, 1)[0]
            break
    else:
        sentence = cleaned

    sentence = sentence.strip().rstrip(".;:!?")
    if not sentence:
        sentence = cleaned

    if len(sentence) > 180:
        sentence = sentence[:180].rsplit(" ", 1)[0]

    sentence = sentence.strip()
    if sentence.endswith("."):
        return sentence
    return f"{sentence}."


def _extract_citations(note: ResearchNote) -> list[str]:
    seen: set[str] = set()
    citations: list[str] = []
    for evidence in note.evidences:
        for candidate in [
            (evidence.citation or "").strip(),
            (evidence.source_ref or "").strip(),
        ]:
            if candidate and candidate not in seen:
                citations.append(candidate)
                seen.add(candidate)
    return citations[:3]


def _manuscript_bullets(
    entries: Sequence[VariantEntry],
    *,
    limit: int,
) -> list[OverviewBullet]:
    bullets: list[OverviewBullet] = []
    for entry in entries[:limit]:
        summary = _summarize_manuscript(entry)
        citations: list[str] = []
        if entry.source:
            citations.append(entry.source)
        if entry.witness and entry.witness not in citations:
            citations.append(entry.witness)
        bullets.append(OverviewBullet(summary=summary, citations=tuple(citations)))
    return bullets


def _summarize_manuscript(entry: VariantEntry) -> str:
    witness = entry.witness or "A manuscript"
    reading = entry.reading.strip() if entry.reading else ""
    note = (entry.note or "").strip()

    parts: list[str] = []
    parts.append(f"{witness} notes this verse.")
    if reading:
        parts.append(f'It reads "{reading}".')
    if note:
        parts.append(_first_sentence(note))
    return " ".join(parts)


__all__ = [
    "OverviewBullet",
    "ReliabilityOverview",
    "build_reliability_overview",
]
