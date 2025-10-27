from __future__ import annotations

from types import SimpleNamespace
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from theo.adapters.persistence.models import AuditLog
from theo.application.facades.database import get_session
from theo.infrastructure.api.app.ai.audit_logging import (
    AuditLogWriter,
    fetch_recent_audit_logs,
    purge_audit_logs,
)
from theo.infrastructure.api.app.ai.rag import GuardrailError, RAGAnswer, RAGCitation
from theo.infrastructure.api.app.main import app
from theo.infrastructure.api.app.routes.ai.workflows import chat as chat_module
from theo.infrastructure.api.app.models import AuditClaimCard, AuditLogMetadata


class DummyRecorder:
    def __init__(self) -> None:
        self.trail = SimpleNamespace(id="trail-stub", mode=None)
        self.finalized: dict[str, object] | None = None

    def __enter__(self) -> "DummyRecorder":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # type: ignore[override]
        return False

    def finalize(
        self,
        *,
        final_md: str | None = None,
        output_payload: object = None,
        status: str = "completed",
    ) -> None:
        self.finalized = {
            "final_md": final_md,
            "output_payload": output_payload,
            "status": status,
        }


class StubTrailService:
    def __init__(self, _session: object) -> None:
        self.recorder = DummyRecorder()

    def start_trail(self, **_: object) -> DummyRecorder:
        return self.recorder

    def resume_trail(self, *_: object, **__: object) -> DummyRecorder:
        return self.recorder


class StubMemoryIndex:
    model_name = "stub-index"

    def embed_entry(self, entry: object) -> None:  # pragma: no cover - interface stub
        return None


def _chat_payload(message: str) -> dict[str, object]:
    return {
        "messages": [{"role": "user", "content": message}],
        "filters": {},
    }


@pytest.fixture
def audit_sessionmaker(api_engine) -> Iterator[sessionmaker]:
    SessionLocal = sessionmaker(bind=api_engine, future=True)
    with SessionLocal() as session:
        session.execute(delete(AuditLog))
        session.commit()
    yield SessionLocal
    with SessionLocal() as session:
        session.execute(delete(AuditLog))
        session.commit()


@pytest.fixture
def chat_audit_client(
    audit_sessionmaker: sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, sessionmaker]]:
    SessionLocal = audit_sessionmaker

    def override_session() -> Iterator[object]:
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_session

    monkeypatch.setattr(chat_module, "TrailService", StubTrailService)
    monkeypatch.setattr(
        chat_module.memory_index_module,
        "get_memory_index",
        lambda: StubMemoryIndex(),
    )
    monkeypatch.setattr(chat_module, "ensure_completion_safe", lambda *_: None)

    try:
        with SessionLocal() as session:
            session.execute(delete(AuditLog))
            session.commit()
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, SessionLocal
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_chat_audit_log_persists_when_persistence_fails(
    chat_audit_client: tuple[TestClient, sessionmaker],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, SessionLocal = chat_audit_client
    citations = [
        RAGCitation(
            index=0,
            osis="John 3:16",
            anchor="John",
            passage_id="passage-1",
            document_id="doc-1",
            snippet="For God so loved the world",
        )
    ]
    answer = RAGAnswer(
        summary="God's love",
        citations=citations,
        model_name="gpt-test",
        model_output="Detailed response",
    )

    monkeypatch.setattr(chat_module, "run_guarded_chat", lambda *_, **__: answer)

    def _fail(*_: object, **__: object) -> None:
        raise RuntimeError("persistence boom")

    monkeypatch.setattr(chat_module, "_persist_chat_session", _fail)

    response = client.post("/ai/chat", json=_chat_payload("Tell me about hope"))
    assert response.status_code == 500

    with SessionLocal() as session:
        records = list(session.execute(select(AuditLog)).scalars())
    assert len(records) == 1
    record = records[0]
    assert record.workflow == "chat"
    assert record.status == "generated"
    assert record.model_preset == "gpt-test"
    assert record.citations and record.citations[0]["osis"] == "John 3:16"


def test_chat_guardrail_refusal_is_logged(
    chat_audit_client: tuple[TestClient, sessionmaker],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, SessionLocal = chat_audit_client

    monkeypatch.setattr(
        chat_module,
        "run_guarded_chat",
        lambda *_, **__: (_ for _ in ()).throw(GuardrailError("blocked")),
    )
    monkeypatch.setattr(chat_module, "_persist_chat_session", lambda *_, **__: None)

    response = client.post("/ai/chat", json=_chat_payload("Unsafe request"))
    assert response.status_code == 422

    with SessionLocal() as session:
        records = list(session.execute(select(AuditLog)).scalars())
    assert len(records) == 1
    record = records[0]
    assert record.workflow == "chat"
    assert record.status == "refused"


def test_audit_log_reporting_and_cleanup(audit_sessionmaker: sessionmaker) -> None:
    SessionLocal = audit_sessionmaker
    with SessionLocal() as session:
        session.execute(delete(AuditLog))
        session.commit()

    with SessionLocal() as session:
        writer = AuditLogWriter.from_session(session)
        writer.log(
            workflow="chat",
            prompt_hash="hash-1",
            model_preset="alpha",
            inputs={"question": "one"},
        )
        writer.log(
            workflow="chat",
            prompt_hash="hash-2",
            model_preset="beta",
            inputs={"question": "two"},
        )
        writer.log(
            workflow="export",
            prompt_hash="hash-3",
            model_preset="gamma",
            inputs={"topic": "three"},
        )

    with SessionLocal() as session:
        recent = fetch_recent_audit_logs(session, limit=5)
        assert len(recent) == 3
        removed = purge_audit_logs(session, keep_latest=1)
        assert removed == 2

    with SessionLocal() as session:
        remaining = fetch_recent_audit_logs(session, limit=5)
        assert len(remaining) == 1
        assert remaining[0].prompt_hash in {"hash-1", "hash-2", "hash-3"}


def test_audit_log_claim_cards_and_metadata(audit_sessionmaker: sessionmaker) -> None:
    SessionLocal = audit_sessionmaker
    with SessionLocal() as session:
        session.execute(delete(AuditLog))
        session.commit()

    claim_card = AuditClaimCard(
        claim_id="c1",
        answer_id="a1",
        text="Example claim",
        mode="Audit-Local",
        label="SUPPORTED",
        confidence=0.92,
        verification_methods=["CoVe", "RAGAS"],
    )
    metadata = AuditLogMetadata(mode="Audit-Local", audit_score=0.88, claim_cards=[claim_card])

    with SessionLocal() as session:
        writer = AuditLogWriter.from_session(session)
        writer.log(
            workflow="chat",
            prompt_hash="hash-claim",
            model_preset="delta",
            inputs={"question": "What is faith?"},
            claim_cards=[claim_card],
            audit_metadata=metadata.model_dump(exclude_none=True),
        )

    with SessionLocal() as session:
        record = session.execute(select(AuditLog)).scalar_one()
        assert record.claim_cards is not None
        assert record.claim_cards[0]["claim_id"] == "c1"
        assert record.audit_metadata is not None
        assert record.audit_metadata["mode"] == "Audit-Local"
