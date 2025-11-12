"""Tests for research note creation and preview workflows."""

from __future__ import annotations

from sqlalchemy.orm import Session

from theo.application.facades.research import ResearchNoteDraft, get_research_service
from theo.adapters.persistence.models import NoteEvidence, ResearchNote


def test_generate_research_note_preview_does_not_persist(
    research_session: Session, research_note_draft: ResearchNoteDraft
) -> None:
    service = get_research_service(research_session)
    preview = service.preview_note(research_note_draft)

    assert preview.osis == "John.1.1"
    assert preview.body.startswith("In the beginning")
    assert len(preview.evidences) == 1
    assert preview.evidences[0].citation == "John 1:1 commentary"

    assert research_session.query(ResearchNote).count() == 0
    assert research_session.query(NoteEvidence).count() == 0


def test_create_research_note_commit_persists(
    research_session: Session, research_note_draft: ResearchNoteDraft
) -> None:
    service = get_research_service(research_session)
    note = service.create_note(research_note_draft, commit=True)

    stored = research_session.get(ResearchNote, note.id)
    assert stored is not None
    assert stored.body == "In the beginning was the Word."
    assert stored.tags == ["gospel", "logos"]
    assert len(stored.evidences) == 1
    assert stored.evidences[0].source_ref == "Example Commentary"
