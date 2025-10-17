"""Tests for research note creation, preview, and MCP tooling."""

from __future__ import annotations

from collections.abc import Iterator, Mapping

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from theo.application.facades.database import Base
from theo.application.facades.research import (
    ResearchNoteDraft,
    ResearchNoteEvidenceDraft,
    get_research_service,
)
from theo.adapters.persistence.models import NoteEvidence, ResearchNote
from theo.services.api.app.mcp.tools import handle_note_write


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


def _draft_from_payload(payload: Mapping[str, object]) -> ResearchNoteDraft:
    tags = payload.get("tags")
    tags_tuple = tuple(tags) if isinstance(tags, list) else None
    evidences_payload = payload.get("evidences")
    evidence_drafts: tuple[ResearchNoteEvidenceDraft, ...] = ()
    if isinstance(evidences_payload, list):
        evidence_drafts = tuple(
            ResearchNoteEvidenceDraft(
                source_type=evidence.get("source_type"),
                source_ref=evidence.get("source_ref"),
                osis_refs=tuple(evidence.get("osis_refs") or []) or None,
                citation=evidence.get("citation"),
                snippet=evidence.get("snippet"),
                meta=evidence.get("meta"),
            )
            for evidence in evidences_payload
        )

    confidence = payload.get("confidence")
    confidence_value = float(confidence) if confidence is not None else None

    return ResearchNoteDraft(
        osis=str(payload.get("osis")),
        body=str(payload.get("body")),
        title=payload.get("title"),
        stance=payload.get("stance"),
        claim_type=payload.get("claim_type"),
        confidence=confidence_value,
        tags=tags_tuple,
        evidences=evidence_drafts,
    )


def test_generate_research_note_preview_does_not_persist(session: Session) -> None:
    service = get_research_service(session)
    preview = service.preview_note(_draft_from_payload(_note_payload()))

    assert preview.osis == "John.1.1"
    assert preview.body.startswith("In the beginning")
    assert len(preview.evidences) == 1
    assert preview.evidences[0].citation == "John 1:1 commentary"

    assert session.query(ResearchNote).count() == 0
    assert session.query(NoteEvidence).count() == 0


def test_create_research_note_commit_persists(session: Session) -> None:
    service = get_research_service(session)
    note = service.create_note(_draft_from_payload(_note_payload()), commit=True)

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
