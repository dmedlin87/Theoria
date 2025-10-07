"""Tests for research note creation, preview, and MCP tooling."""

from __future__ import annotations

from collections.abc import Iterator, Mapping

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from theo.services.api.app.core.database import Base
from theo.services.api.app.db.models import NoteEvidence, ResearchNote
from theo.services.api.app.mcp.tools import handle_note_write
from theo.services.api.app.research.notes import (
    create_research_note,
    generate_research_note_preview,
)


@pytest.fixture()
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    db_session = TestingSession()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _note_payload() -> Mapping[str, object]:
    return {
        "osis": "John.1.1",
        "body": "In the beginning was the Word.",
        "title": "Prologue",
        "stance": "neutral",
        "claim_type": "observation",
        "confidence": 0.8,
        "tags": ["gospel", "logos"],
        "evidences": [
            {
                "source_type": "commentary",
                "source_ref": "Example Commentary",
                "osis_refs": ["John.1.1"],
                "citation": "John 1:1 commentary",
                "snippet": "The Word refers to Jesus.",
                "meta": {"publisher": "Test Press"},
            }
        ],
    }


def test_generate_research_note_preview_does_not_persist(session: Session) -> None:
    preview = generate_research_note_preview(session, **_note_payload())

    assert preview.osis == "John.1.1"
    assert preview.body.startswith("In the beginning")
    assert len(preview.evidences) == 1
    assert preview.evidences[0].citation == "John 1:1 commentary"

    assert session.query(ResearchNote).count() == 0
    assert session.query(NoteEvidence).count() == 0


def test_create_research_note_commit_persists(session: Session) -> None:
    note = create_research_note(session, **_note_payload(), commit=True)

    stored = session.get(ResearchNote, note.id)
    assert stored is not None
    assert stored.body == "In the beginning was the Word."
    assert stored.tags == ["gospel", "logos"]
    assert len(stored.evidences) == 1
    assert stored.evidences[0].source_ref == "Example Commentary"


def test_handle_note_write_commit_flag_controls_persistence(session: Session) -> None:
    dry_run = handle_note_write(session, {**_note_payload(), "commit": False})

    assert dry_run.osis == "John.1.1"
    assert session.query(ResearchNote).count() == 0
    assert session.query(NoteEvidence).count() == 0

    committed = handle_note_write(session, _note_payload())

    assert session.query(ResearchNote).count() == 1
    assert session.query(NoteEvidence).count() == 1

    stored = session.get(ResearchNote, committed.id)
    assert stored is not None
    assert stored.body == committed.body
