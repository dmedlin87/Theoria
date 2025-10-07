"""Persistence helpers for Living Notes."""

from __future__ import annotations

from typing import Any, Iterable

from fastapi import HTTPException
from sqlalchemy import Text, cast, func
from sqlalchemy.orm import Session

from ..db.models import NoteEvidence, ResearchNote
from ..models.research import ResearchNote as ResearchNoteSchema


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
    commit: bool = True,
    request_id: str | None = None,
    end_user_id: str | None = None,
    tenant_id: str | None = None,
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
        request_id=request_id,
        created_by=end_user_id,
        tenant_id=tenant_id,
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

    session.flush()

    if commit:
        session.commit()
        session.refresh(note)
    return note


def generate_research_note_preview(
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
) -> ResearchNoteSchema:
    """Render a research note preview without committing it to the database."""

    transaction = session.begin_nested()
    try:
        note = create_research_note(
            session,
            osis=osis,
            body=body,
            title=title,
            stance=stance,
            claim_type=claim_type,
            confidence=confidence,
            tags=tags,
            evidences=evidences,
            commit=False,
        )
        session.flush()
        preview = ResearchNoteSchema.model_validate(note)
    finally:
        if transaction.is_active:
            transaction.rollback()

    return preview


def get_notes_for_osis(
    session: Session,
    osis: str,
    *,
    stance: str | None = None,
    claim_type: str | None = None,
    tag: str | None = None,
    min_confidence: float | None = None,
) -> list[ResearchNote]:
    """Return all notes linked to a given OSIS reference with optional filters."""

    query = session.query(ResearchNote).filter(ResearchNote.osis == osis)

    if stance:
        stance_normalized = stance.lower()
        query = query.filter(
            ResearchNote.stance.is_not(None),
            func.lower(ResearchNote.stance) == stance_normalized,
        )

    if claim_type:
        claim_normalized = claim_type.lower()
        query = query.filter(
            ResearchNote.claim_type.is_not(None),
            func.lower(ResearchNote.claim_type) == claim_normalized,
        )

    if tag:
        tag_pattern = f'%"{tag.lower()}"%'
        query = query.filter(
            ResearchNote.tags.is_not(None),
            func.lower(cast(ResearchNote.tags, Text)).like(tag_pattern),
        )

    if min_confidence is not None:
        query = query.filter(ResearchNote.confidence >= min_confidence)

    return query.order_by(ResearchNote.created_at.desc()).all()


def update_research_note(
    session: Session,
    note_id: str,
    *,
    changes: dict[str, Any],
    evidences: Iterable[dict] | None = None,
) -> ResearchNote:
    """Update persisted note fields and optionally replace evidence rows."""

    note = session.get(ResearchNote, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Research note not found")

    for field, value in changes.items():
        if field == "tags":
            note.tags = list(value) if value is not None else None
        elif field in {"osis", "body", "title", "stance", "claim_type", "confidence"}:
            setattr(note, field, value)

    if evidences is not None:
        note.evidences.clear()
        session.flush()
        for evidence in evidences:
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


def delete_research_note(session: Session, note_id: str) -> None:
    """Remove a research note and cascade-delete evidence rows."""

    note = session.get(ResearchNote, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Research note not found")

    session.delete(note)
    session.commit()
