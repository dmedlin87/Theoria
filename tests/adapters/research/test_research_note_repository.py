from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy.orm import Session

from theo.adapters.persistence.models import NoteEvidence, ResearchNote as ResearchNoteModel
from theo.adapters.research.sqlalchemy import SqlAlchemyResearchNoteRepository
from theo.domain.research import (
    ResearchNoteDraft,
    ResearchNoteEvidenceDraft,
    ResearchNoteNotFoundError,
)


def _with(base: ResearchNoteDraft, **overrides: object) -> ResearchNoteDraft:
    """Return a copy of *base* with the provided overrides applied."""

    return replace(base, **overrides)


def _refresh_model(session: Session, note_id: str) -> ResearchNoteModel:
    session.expire_all()
    return session.get(ResearchNoteModel, note_id)


def test_create_persists_note_and_evidences(
    research_session: Session, research_note_draft: ResearchNoteDraft
) -> None:
    repo = SqlAlchemyResearchNoteRepository(research_session)

    result = repo.create(research_note_draft)

    assert result.title == research_note_draft.title
    assert result.tags == research_note_draft.tags
    assert len(result.evidences) == 1

    stored = research_session.query(ResearchNoteModel).one()
    assert stored.request_id == research_note_draft.request_id
    assert stored.tags == list(research_note_draft.tags or [])
    assert len(stored.evidences) == 1
    evidence = stored.evidences[0]
    assert evidence.source_ref == result.evidences[0].source_ref
    assert evidence.meta == result.evidences[0].meta


def test_preview_rolls_back_transaction(
    research_session: Session, research_note_draft: ResearchNoteDraft
) -> None:
    repo = SqlAlchemyResearchNoteRepository(research_session)

    preview = repo.preview(research_note_draft)

    assert preview.id is not None
    assert research_session.query(ResearchNoteModel).count() == 0


def test_list_for_osis_applies_filters(
    research_session: Session, research_note_draft: ResearchNoteDraft
) -> None:
    repo = SqlAlchemyResearchNoteRepository(research_session)
    recent = repo.create(
        _with(
            research_note_draft,
            osis="Rom.8.1",
            stance="supporting",
            claim_type="theology",
            tags=("freedom", "spirit"),
            confidence=0.8,
        )
    )
    repo.create(
        _with(
            research_note_draft,
            osis="Rom.8.1",
            stance="opposing",
            claim_type="doctrine",
            tags=("bondage",),
            confidence=0.7,
        )
    )

    results = repo.list_for_osis(
        "Rom.8.1",
        stance="Supporting",
        claim_type="Theology",
        tag="spirit",
        min_confidence=0.75,
    )

    assert [note.id for note in results] == [recent.id]
    assert results[0].tags == ("freedom", "spirit")


def test_update_replaces_evidences(
    research_session: Session, research_note_draft: ResearchNoteDraft
) -> None:
    repo = SqlAlchemyResearchNoteRepository(research_session)
    created = repo.create(research_note_draft)

    new_evidence = ResearchNoteEvidenceDraft(
        source_type="commentary",
        source_ref="Matthew Henry",
        citation="Henry on John 3:16",
        snippet="Commentary snippet",
    )
    updated = repo.update(
        created.id,
        {"title": "Renewed", "tags": ("renewed", "love")},
        evidences=(new_evidence,),
    )

    assert updated.title == "Renewed"
    assert updated.tags == ("renewed", "love")
    assert len(updated.evidences) == 1
    assert updated.evidences[0].source_type == "commentary"

    stored = _refresh_model(research_session, created.id)
    assert stored.title == "Renewed"
    assert stored.tags == ["renewed", "love"]
    assert len(stored.evidences) == 1
    assert stored.evidences[0].source_ref == "Matthew Henry"


def test_delete_removes_note_and_evidence(
    research_session: Session, research_note_draft: ResearchNoteDraft
) -> None:
    repo = SqlAlchemyResearchNoteRepository(research_session)
    created = repo.create(research_note_draft)

    repo.delete(created.id)

    assert research_session.get(ResearchNoteModel, created.id) is None
    assert research_session.query(NoteEvidence).count() == 0


def test_update_missing_note_raises(research_session: Session) -> None:
    repo = SqlAlchemyResearchNoteRepository(research_session)

    with pytest.raises(ResearchNoteNotFoundError):
        repo.update("missing", {"title": "Nope"})
