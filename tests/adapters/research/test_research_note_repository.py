from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from theo.adapters.persistence import Base
from theo.adapters.persistence.models import NoteEvidence, ResearchNote as ResearchNoteModel
from theo.adapters.research.sqlalchemy import SqlAlchemyResearchNoteRepository
from theo.domain.research import (
    ResearchNoteDraft,
    ResearchNoteEvidenceDraft,
    ResearchNoteNotFoundError,
)


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _draft(**overrides) -> ResearchNoteDraft:
    base = dict(
        osis="John.3.16",
        body="God so loved the world",
        title="Love",
        stance="supporting",
        claim_type="doctrine",
        confidence=0.9,
        tags=("love", "grace"),
        evidences=(
            ResearchNoteEvidenceDraft(
                source_type="scripture",
                source_ref="John 3:16",
                osis_refs=("John.3.16",),
                citation="John 3:16",
                snippet="For God so loved the world",
                meta={"translation": "ESV"},
            ),
        ),
        request_id="req-1",
        end_user_id="user-1",
        tenant_id="tenant-1",
    )
    base.update(overrides)
    return ResearchNoteDraft(**base)


def _refresh_model(session: Session, note_id: str) -> ResearchNoteModel:
    session.expire_all()
    return session.get(ResearchNoteModel, note_id)


def test_create_persists_note_and_evidences(session: Session) -> None:
    repo = SqlAlchemyResearchNoteRepository(session)

    result = repo.create(_draft())

    assert result.title == "Love"
    assert result.tags == ("love", "grace")
    assert len(result.evidences) == 1

    stored = session.query(ResearchNoteModel).one()
    assert stored.request_id == "req-1"
    assert stored.tags == ["love", "grace"]
    assert len(stored.evidences) == 1
    evidence = stored.evidences[0]
    assert evidence.source_ref == "John 3:16"
    assert evidence.meta == {"translation": "ESV"}


def test_preview_rolls_back_transaction(session: Session) -> None:
    repo = SqlAlchemyResearchNoteRepository(session)

    preview = repo.preview(_draft())

    assert preview.id is not None
    assert session.query(ResearchNoteModel).count() == 0


def test_list_for_osis_applies_filters(session: Session) -> None:
    repo = SqlAlchemyResearchNoteRepository(session)
    recent = repo.create(
        _draft(
            osis="Rom.8.1",
            stance="supporting",
            claim_type="theology",
            tags=("freedom", "spirit"),
            confidence=0.8,
        )
    )
    repo.create(
        _draft(
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


def test_update_replaces_evidences(session: Session) -> None:
    repo = SqlAlchemyResearchNoteRepository(session)
    created = repo.create(_draft())

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

    stored = _refresh_model(session, created.id)
    assert stored.title == "Renewed"
    assert stored.tags == ["renewed", "love"]
    assert len(stored.evidences) == 1
    assert stored.evidences[0].source_ref == "Matthew Henry"


def test_delete_removes_note_and_evidence(session: Session) -> None:
    repo = SqlAlchemyResearchNoteRepository(session)
    created = repo.create(_draft())

    repo.delete(created.id)

    assert session.get(ResearchNoteModel, created.id) is None
    assert session.query(NoteEvidence).count() == 0


def test_update_missing_note_raises(session: Session) -> None:
    repo = SqlAlchemyResearchNoteRepository(session)

    with pytest.raises(ResearchNoteNotFoundError):
        repo.update("missing", {"title": "Nope"})
