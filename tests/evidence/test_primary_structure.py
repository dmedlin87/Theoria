"""Integration tests for evidence card persistence helpers."""

from __future__ import annotations

import pytest

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker
    from theo.infrastructure.api.app.persistence_models import Base, EvidenceCard
    from theo.infrastructure.api.app.research.evidence_cards import (
        create_evidence_card,
        preview_evidence_card,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - dependency missing in CI
    pytest.skip(f"dependency not available: {exc}", allow_module_level=True)
except ImportError as exc:  # pragma: no cover - dependency missing in CI
    pytest.skip(f"dependency not available: {exc}", allow_module_level=True)


@pytest.fixture()
def sqlite_session(tmp_path) -> Session:
    engine = create_engine(f"sqlite:///{tmp_path/'evidence.db'}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    try:
        yield session
        session.rollback()
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_create_evidence_card_trims_and_normalizes(sqlite_session: Session) -> None:
    card = create_evidence_card(
        sqlite_session,
        osis="John.1.1",
        claim_summary="  Logos and Creation  ",
        evidence={"kind": "quote", "text": "In the beginning"},
        tags=["faith", "FAITH", " context "],
        commit=False,
        request_id="req-1",
        end_user_id="user-9",
        tenant_id="tenant-a",
    )
    sqlite_session.flush()

    refreshed = sqlite_session.get(EvidenceCard, card.id)

    assert refreshed is not None
    assert refreshed.claim_summary == "Logos and Creation"
    assert refreshed.tags == ["context", "faith"]
    assert refreshed.request_id == "req-1"
    assert refreshed.created_by == "user-9"
    assert refreshed.tenant_id == "tenant-a"
    assert refreshed.evidence == {"kind": "quote", "text": "In the beginning"}


def test_preview_evidence_card_rolls_back(sqlite_session: Session) -> None:
    preview = preview_evidence_card(
        sqlite_session,
        osis="Gen.1.1",
        claim_summary=" In the beginning God created ",
        evidence={"kind": "summary", "text": "Creation narrative"},
        tags=["creation", "Creation"],
    )

    assert preview == {
        "osis": "Gen.1.1",
        "claim_summary": "In the beginning God created",
        "evidence": {"kind": "summary", "text": "Creation narrative"},
        "tags": ["Creation", "creation"],
    }

    sqlite_session.expire_all()
    assert sqlite_session.query(EvidenceCard).count() == 0
