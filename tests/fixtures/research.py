"""Fixtures seeding research note data for tests."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING

import importlib.util
import pytest

RESEARCH_DEPENDENCIES_AVAILABLE = True
RESEARCH_IMPORT_ERROR: Exception | None = None

try:  # pragma: no cover - optional dependency wiring
    sqlalchemy_spec = importlib.util.find_spec("sqlalchemy")
    theo_spec = importlib.util.find_spec("theo")
    if sqlalchemy_spec is None or theo_spec is None:
        raise ModuleNotFoundError("research fixtures dependencies not available")
except (ModuleNotFoundError, ImportError) as exc:  # pragma: no cover - dependency missing
    RESEARCH_DEPENDENCIES_AVAILABLE = False
    RESEARCH_IMPORT_ERROR = exc
    Session = None  # type: ignore[assignment]
    sessionmaker = None  # type: ignore[assignment]
    StaticPool = None  # type: ignore[assignment]
    SqlAlchemyResearchNoteRepository = None  # type: ignore[assignment]
    Base = None  # type: ignore[assignment]
    ResearchNote = None  # type: ignore[assignment]
    ResearchNoteDraft = None  # type: ignore[assignment]
    ResearchNoteEvidenceDraft = None  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover - typing only
    from sqlalchemy.orm import Session as SQLASession
else:  # pragma: no cover - runtime fallback
    SQLASession = object


def _require_dependencies() -> None:
    if not RESEARCH_DEPENDENCIES_AVAILABLE:
        pytest.skip(f"sqlalchemy dependency not available: {RESEARCH_IMPORT_ERROR}")


def _draft_from_payload(payload: Mapping[str, object]) -> ResearchNoteDraft:
    _require_dependencies()

    from theo.domain.research import ResearchNoteDraft, ResearchNoteEvidenceDraft

    tags = payload.get("tags")
    tags_tuple: tuple[str, ...] | None = None
    if isinstance(tags, (list, tuple)):
        tags_tuple = tuple(str(tag) for tag in tags if tag)

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
        request_id=payload.get("request_id"),
        end_user_id=payload.get("end_user_id"),
        tenant_id=payload.get("tenant_id"),
    )


@pytest.fixture()
def research_note_payload() -> dict[str, object]:
    """Return a canonical research note payload used across tests."""

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
        "request_id": "req-1",
        "end_user_id": "user-1",
        "tenant_id": "tenant-1",
    }


@pytest.fixture()
def research_note_draft(research_note_payload: Mapping[str, object]) -> ResearchNoteDraft:
    """Return a draft constructed from the canonical research note payload."""

    return _draft_from_payload(research_note_payload)


@pytest.fixture()
def research_session() -> Iterator[SQLASession]:
    """Provide an isolated in-memory SQLite session for research tests."""

    _require_dependencies()

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from theo.application.facades.database import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
        expire_on_commit=False,
    )
    session = SessionLocal()
    try:
        yield session
        session.rollback()
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def persisted_research_note(
    research_session: SQLASession, research_note_draft: ResearchNoteDraft
) -> ResearchNote:
    """Persist the canonical research note and return the stored aggregate."""

    _require_dependencies()

    from theo.adapters.research.sqlalchemy import SqlAlchemyResearchNoteRepository

    repository = SqlAlchemyResearchNoteRepository(research_session)
    note = repository.create(research_note_draft, commit=True)
    return note
