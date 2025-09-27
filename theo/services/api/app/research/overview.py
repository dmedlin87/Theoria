"""Helpers for building a reliability overview snapshot for a verse."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy.orm import Session

from ..db.models import NoteEvidence, ResearchNote
from .notes import get_notes_for_osis
from .variants import VariantEntry, variants_apparatus

SUPPORTED_MODES = {"apologetic", "skeptical"}
SUPPORTIVE_STANCES = {"apologetic", "supportive", "harmonizing", "pro"}
CRITICAL_STANCES = {"skeptical", "critical", "contrary", "challenge"}
NEUTRAL_STANCES = {"neutral", "background"}


@dataclass(slots=True)
class OverviewBullet:
    summary: str
    citations: list[str]


@dataclass(slots=True)
class ReliabilityOverview:
    osis: str
    mode: str
    consensus: list[OverviewBullet]
    disputed: list[OverviewBullet]
    manuscripts: list[OverviewBullet]


def build_reliability_overview(
    session: Session,
    osis: str,
    *,
    mode: str | None = None,
    note_limit: int = 3,
    manuscript_limit: int = 3,
) -> ReliabilityOverview:
    """Construct a compact overview balancing consensus and disputed claims."""

    normalized_mode = (mode or "apologetic").lower()
    if normalized_mode not in SUPPORTED_MODES:
        normalized_mode = "apologetic"

    notes = get_notes_for_osis(session, osis)

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
            # Unknown stance gets treated as neutral, keeping copy even-handed.
            neutral.append(bullet)

    if normalized_mode == "skeptical":
        consensus = (critical + neutral)[:note_limit]
        disputed = supportive[:note_limit]
    else:
        consensus = (supportive + neutral)[:note_limit]
        disputed = critical[:note_limit]

    manuscripts = _manuscript_bullets(osis, limit=manuscript_limit)

    return ReliabilityOverview(
        osis=osis,
        mode=normalized_mode,
        consensus=consensus,
        disputed=disputed,
        manuscripts=manuscripts,
    )


def _note_to_bullet(note: ResearchNote) -> OverviewBullet | None:
    """Translate a research note into a short, reader-friendly bullet."""

    text_source = (note.title or "").strip() or (note.body or "").strip()
    if not text_source:
        return None

    summary = _first_sentence(text_source)
    citations = _extract_citations(note.evidences)
    return OverviewBullet(summary=summary, citations=citations)


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


def _extract_citations(evidences: Sequence[NoteEvidence]) -> list[str]:
    seen: set[str] = set()
    citations: list[str] = []
    for evidence in evidences:
        for candidate in [
            (evidence.citation or "").strip(),
            (evidence.source_ref or "").strip(),
        ]:
            if candidate and candidate not in seen:
                citations.append(candidate)
                seen.add(candidate)
    return citations[:3]


def _manuscript_bullets(osis: str, *, limit: int) -> list[OverviewBullet]:
    entries = variants_apparatus(osis, categories=["manuscript"], limit=limit)
    bullets: list[OverviewBullet] = []
    for entry in entries:
        summary = _summarize_manuscript(entry)
        citations = []
        if entry.source:
            citations.append(entry.source)
        if entry.witness and entry.witness not in citations:
            citations.append(entry.witness)
        bullets.append(OverviewBullet(summary=summary, citations=citations))
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

