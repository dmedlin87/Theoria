"""Persistence helpers for Living Notes."""

from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from ..db.models import NoteEvidence, ResearchNote


def create_research_note(
    session: Session,
    *,
    osis: str,
    body: str,
    title: str | None = None,
    stance: str | None = None,
    claim_type: str | None = None,
    confidence: float | None = None,
    tags: list[str] | None = None,
    evidences: Iterable[dict] | None = None,
) -> ResearchNote:
    """Persist a research note and optional evidence records."""

    note = ResearchNote(
        osis=osis,
        body=body,
        title=title,
        stance=stance,
        claim_type=claim_type,
        confidence=confidence,
        tags=list(tags) if tags else None,
    )
    session.add(note)
    session.flush()

    for evidence in evidences or []:
        note.evidences.append(
            NoteEvidence(
                source_type=evidence.get("source_type"),
                source_ref=evidence.get("source_ref"),
                osis_refs=evidence.get("osis_refs"),
                citation=evidence.get("citation"),
                snippet=evidence.get("snippet"),
                meta=evidence.get("meta"),
            )
        )

    session.commit()
    session.refresh(note)
    return note


def get_notes_for_osis(session: Session, osis: str) -> list[ResearchNote]:
    """Return all notes linked to a given OSIS reference."""

    return (
        session.query(ResearchNote)
        .filter(ResearchNote.osis == osis)
        .order_by(ResearchNote.created_at.desc())
        .all()
    )
