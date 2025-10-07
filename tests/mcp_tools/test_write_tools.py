from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from mcp_server import schemas
from mcp_server.security import reset_write_security_policy
from mcp_server.tools import write


@contextmanager
def _fake_session_scope():
    yield SimpleNamespace()


@pytest.fixture(autouse=True)
def reset_policy(monkeypatch):
    reset_write_security_policy()
    monkeypatch.delenv("MCP_WRITE_ALLOWLIST", raising=False)
    monkeypatch.delenv("MCP_WRITE_RATE_LIMITS", raising=False)
    monkeypatch.setattr(write, "_session_scope", _fake_session_scope)
    yield
    reset_write_security_policy()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio("asyncio")
async def test_note_write_preview_default(monkeypatch):
    preview = SimpleNamespace(
        osis="John.1.1",
        title="Logos",
        stance="affirmative",
        claim_type="doctrine",
        tags=["Logos", "Word"],
        body="In the beginning was the Word",
    )
    monkeypatch.setattr(write, "generate_research_note_preview", lambda session, **_: preview)

    request = schemas.NoteWriteRequest(
        request_id="req-note-1",
        osis="John.1.1",
        body="In the beginning was the Word",
    )

    response = await write.note_write(request, end_user_id="user-1")
    assert response.commit is False
    assert response.status == "preview"
    assert response.preview == {
        "osis": "John.1.1",
        "title": "Logos",
        "stance": "affirmative",
        "claim_type": "doctrine",
        "tags": ["Logos", "Word"],
        "body": "In the beginning was the Word",
    }


@pytest.mark.anyio("asyncio")
async def test_note_write_commit_invokes_creator(monkeypatch):
    calls: list[dict[str, object]] = []

    def _create_note(session, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(id="note-123")

    monkeypatch.setattr(write, "create_research_note", _create_note)

    request = schemas.NoteWriteRequest(
        request_id="req-note-2",
        osis="John.1.1",
        body="In the beginning",
        commit=True,
    )

    response = await write.note_write(
        request,
        end_user_id="user-99",
        tenant_id="tenant-A",
        idempotency_key="idem-1",
    )

    assert response.commit is True
    assert response.note_id == "note-123"
    assert calls and calls[0]["request_id"] == "req-note-2"
    assert calls[0]["end_user_id"] == "user-99"
    assert calls[0]["tenant_id"] == "tenant-A"

    # Idempotent replay should return cached response and not invoke creator again.
    second = await write.note_write(
        request,
        end_user_id="user-99",
        tenant_id="tenant-A",
        idempotency_key="idem-1",
    )
    assert second.note_id == "note-123"
    assert len(calls) == 1


@pytest.mark.anyio("asyncio")
async def test_note_write_respects_allowlist(monkeypatch):
    monkeypatch.setenv("MCP_WRITE_ALLOWLIST", "note_write=tenant-allowed")
    reset_write_security_policy()

    request = schemas.NoteWriteRequest(
        request_id="req-note-3",
        osis="John.1.1",
        body="Preview",
        commit=True,
    )

    with pytest.raises(HTTPException) as excinfo:
        await write.note_write(request, end_user_id="user-2", tenant_id="tenant-blocked")
    assert excinfo.value.status_code == 403


@pytest.mark.anyio("asyncio")
async def test_note_write_rate_limited(monkeypatch):
    monkeypatch.setenv("MCP_WRITE_RATE_LIMITS", "note_write=1")
    reset_write_security_policy()

    request = schemas.NoteWriteRequest(
        request_id="req-note-4",
        osis="John.1.1",
        body="Commit once",
        commit=True,
    )

    monkeypatch.setattr(write, "create_research_note", lambda session, **_: SimpleNamespace(id="note-456"))

    await write.note_write(request, end_user_id="user-3")

    with pytest.raises(HTTPException) as excinfo:
        await write.note_write(request, end_user_id="user-3")
    assert excinfo.value.status_code == 429


@pytest.mark.anyio("asyncio")
async def test_index_refresh_preview_surfaces_payload(monkeypatch):
    called = False

    def _enqueue(*_, **__):  # pragma: no cover - should not be hit
        nonlocal called
        called = True
        return SimpleNamespace(model_dump=lambda: {"id": "job-1"})

    monkeypatch.setattr(write, "enqueue_refresh_hnsw_job", _enqueue)

    request = schemas.IndexRefreshRequest(
        request_id="req-refresh-1",
        sample_queries=50,
        top_k=20,
    )

    response = await write.index_refresh(request, end_user_id="user-4")
    assert response.commit is False
    assert response.preview == {"sample_queries": 50, "top_k": 20}
    assert called is False


@pytest.mark.anyio("asyncio")
async def test_index_refresh_commit_invokes_enqueue(monkeypatch):
    jobs: list[dict[str, object]] = []

    class _Job:
        def __init__(self, payload):
            self.payload = payload

        def model_dump(self):
            return self.payload

    def _enqueue(request, session):
        jobs.append({"sample_queries": request.sample_queries, "top_k": request.top_k})
        return _Job({"id": "job-77", "status": "queued"})

    monkeypatch.setattr(write, "enqueue_refresh_hnsw_job", _enqueue)

    request = schemas.IndexRefreshRequest(
        request_id="req-refresh-2",
        sample_queries=5,
        top_k=3,
        commit=True,
    )

    response = await write.index_refresh(
        request,
        end_user_id="user-5",
        tenant_id="tenant-B",
        idempotency_key="idem-refresh",
    )

    assert jobs == [{"sample_queries": 5, "top_k": 3}]
    assert response.commit is True
    assert response.job == {"id": "job-77", "status": "queued"}

    second = await write.index_refresh(
        request,
        end_user_id="user-5",
        tenant_id="tenant-B",
        idempotency_key="idem-refresh",
    )
    assert second.job == {"id": "job-77", "status": "queued"}
    assert len(jobs) == 1


@pytest.mark.anyio("asyncio")
async def test_evidence_card_preview_and_commit(monkeypatch):
    previews: dict[str, object] = {
        "osis": "Acts.17.11",
        "claim_summary": "Bereans examined the scriptures",
        "evidence": {"source": "Acts"},
        "tags": ["Bereans"],
    }

    monkeypatch.setattr(write, "preview_evidence_card", lambda session, **_: previews)

    request = schemas.EvidenceCardCreateRequest(
        request_id="req-ev-1",
        osis="Acts.17.11",
        claim_summary="Bereans examined",
        evidence={"source": "Acts"},
    )

    preview_response = await write.evidence_card_create(request, end_user_id="user-6")
    assert preview_response.commit is False
    assert preview_response.preview == {
        "osis": "Acts.17.11",
        "claim_summary": "Bereans examined the scriptures",
        "evidence": {"source": "Acts"},
        "tags": ["Bereans"],
    }

    creations: list[dict[str, object]] = []

    def _create_card(session, **kwargs):
        creations.append(kwargs)
        return SimpleNamespace(id="evidence-1")

    monkeypatch.setattr(write, "create_evidence_card", _create_card)

    commit_request = request.model_copy(update={"commit": True})
    commit_response = await write.evidence_card_create(
        commit_request,
        end_user_id="user-6",
        tenant_id="tenant-C",
    )

    assert commit_response.commit is True
    assert commit_response.evidence_id == "evidence-1"
    assert creations[0]["end_user_id"] == "user-6"
    assert creations[0]["tenant_id"] == "tenant-C"


@pytest.mark.anyio("asyncio")
async def test_evidence_card_idempotency(monkeypatch):
    created: list[str] = []

    def _create_card(session, **_):
        created.append("called")
        return SimpleNamespace(id="evidence-2")

    monkeypatch.setattr(write, "create_evidence_card", _create_card)

    request = schemas.EvidenceCardCreateRequest(
        request_id="req-ev-2",
        osis="Acts.17.11",
        claim_summary="Bereans examined",
        evidence={"source": "Acts"},
        commit=True,
    )

    await write.evidence_card_create(
        request,
        end_user_id="user-7",
        idempotency_key="idemp-ev",
    )
    await write.evidence_card_create(
        request,
        end_user_id="user-7",
        idempotency_key="idemp-ev",
    )

    assert created == ["called"]
