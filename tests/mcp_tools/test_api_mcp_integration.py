"""Integration tests for MCP API tools."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Iterable

import pytest

from theo.infrastructure.api.app.mcp import tools
from theo.infrastructure.api.app.mcp.tools import MCPToolError
from theo.infrastructure.api.app.models.research import ResearchNote as ResearchNoteSchema


_FAKE_TIMESTAMP = datetime(2024, 1, 1, tzinfo=timezone.utc)


@dataclass
class _FakeResult:
    rows: Iterable[Any]

    def __iter__(self):
        return iter(self.rows)


@dataclass
class _FakeSession:
    rows: Iterable[Any]

    def execute(self, _stmt):
        return _FakeResult(self.rows)


class _FakeResearchService:
    def __init__(self):
        self.created: list[tuple[Any, bool]] = []
        self.previewed: list[Any] = []

    def create_note(self, draft, *, commit: bool = True):
        self.created.append((draft, commit))
        return ResearchNoteSchema(
            id="note-created",
            osis=draft.osis,
            body=draft.body,
            title=draft.title,
            stance=draft.stance,
            claim_type=draft.claim_type,
            confidence=None,
            tags=list(draft.tags or []) or None,
            evidences=[],
            created_at=_FAKE_TIMESTAMP,
            updated_at=_FAKE_TIMESTAMP,
        )

    def preview_note(self, draft):
        self.previewed.append(draft)
        return ResearchNoteSchema(
            id="note-preview",
            osis=draft.osis,
            body=draft.body,
            title=draft.title,
            stance=draft.stance,
            claim_type=draft.claim_type,
            confidence=None,
            tags=list(draft.tags or []) or None,
            evidences=[],
            created_at=_FAKE_TIMESTAMP,
            updated_at=_FAKE_TIMESTAMP,
        )


@pytest.fixture
def fake_service(monkeypatch):
    service = _FakeResearchService()
    monkeypatch.setattr(tools, "get_research_service", lambda session: service)
    return service


def _build_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "osis": "John.3.16",
        "body": "For God so loved the world",
        "title": "Gospel Insight",
        "stance": "supportive",
        "claim_type": "commentary",
        "tags": ["grace", "love"],
        "evidences": [
            {
                "source_type": "passage",
                "source_ref": "doc-1",
                "osis_refs": ["John.3.16"],
                "citation": "John 3:16",
                "snippet": "For God so loved the world",
                "meta": {"translation": "KJV"},
            }
        ],
    }
    payload.update(overrides)
    return payload


class TestHandleNoteWrite:
    def test_commits_by_default(self, fake_service):
        payload = _build_payload()
        session = SimpleNamespace()

        response = tools.handle_note_write(session, payload)

        assert response.osis == "John.3.16"
        assert fake_service.created, "create_note should be invoked"
        draft, commit_flag = fake_service.created[-1]
        assert commit_flag is True
        assert list(draft.tags) == ["grace", "love"]
        assert len(draft.evidences) == 1
        evidence = draft.evidences[0]
        assert list(evidence.osis_refs) == ["John.3.16"]
        assert evidence.meta == {"translation": "KJV"}

    def test_preview_when_commit_false(self, fake_service):
        payload = _build_payload(commit=False)
        session = SimpleNamespace()

        response = tools.handle_note_write(session, payload)

        assert not fake_service.created
        assert fake_service.previewed, "preview_note should be invoked"
        preview_draft = fake_service.previewed[-1]
        assert preview_draft.osis == "John.3.16"
        assert response.body == payload["body"]

    def test_doc_id_used_when_osis_missing(self, fake_service, monkeypatch):
        payload = _build_payload(osis="   ", doc_id="doc-77")
        session = SimpleNamespace()

        orig_resolver = tools._resolve_document_osis

        def fake_resolver(sess, doc_id):
            assert sess is session
            if doc_id == "doc-77":
                return "Gen.1.1"
            return orig_resolver(sess, doc_id)

        monkeypatch.setattr(tools, "_resolve_document_osis", fake_resolver)

        tools.handle_note_write(session, payload)

        draft, _ = fake_service.created[-1]
        assert draft.osis == "Gen.1.1"

    def test_missing_osis_raises_error(self, fake_service, monkeypatch):
        payload = _build_payload(osis="", doc_id=None)
        session = SimpleNamespace()

        orig_resolver = tools._resolve_document_osis

        def always_none_resolver(sess, doc_id):
            if isinstance(doc_id, str):
                return orig_resolver(sess, doc_id)
            return None

        monkeypatch.setattr(tools, "_resolve_document_osis", always_none_resolver)

        with pytest.raises(MCPToolError) as exc:
            tools.handle_note_write(session, payload)

        assert "OSIS reference" in str(exc.value)

    def test_invalid_payload_raises_mcp_error(self, fake_service):
        payload = {"osis": "", "body": None}
        session = SimpleNamespace()

        with pytest.raises(MCPToolError):
            tools.handle_note_write(session, payload)


class TestResolveDocumentOsis:
    def test_prefers_primary_reference(self, monkeypatch):
        rows = [
            SimpleNamespace(osis_ref="Gen.1.1", meta={"osis_primary": "Gen.1.2"}),
            SimpleNamespace(osis_ref="Gen.1.3", meta={}),
        ]
        session = _FakeSession(rows)
        monkeypatch.setattr(tools, "get_research_service", lambda s: _FakeResearchService())
        payload = _build_payload(osis=" ", doc_id="doc-1")
        orig_resolver = tools._resolve_document_osis

        def patched_resolver(sess, doc_id):
            assert sess is session
            return orig_resolver(sess, doc_id)

        monkeypatch.setattr(tools, "_resolve_document_osis", patched_resolver)
        result = tools.handle_note_write(session, payload)
        assert result.osis == "Gen.1.2"

    def test_falls_back_to_first_osis(self, monkeypatch):
        rows = [
            SimpleNamespace(osis_ref="Gen.1.4", meta=None),
            SimpleNamespace(osis_ref="Gen.1.5", meta="not-a-mapping"),
        ]
        session = _FakeSession(rows)
        monkeypatch.setattr(tools, "get_research_service", lambda s: _FakeResearchService())
        payload = _build_payload(osis=" ", doc_id="doc-2")
        orig_resolver = tools._resolve_document_osis

        def patched_resolver(sess, doc_id):
            assert sess is session
            return orig_resolver(sess, doc_id)

        monkeypatch.setattr(tools, "_resolve_document_osis", patched_resolver)
        result = tools.handle_note_write(session, payload)
        assert result.osis == "Gen.1.4"

    def test_returns_none_when_no_rows(self, monkeypatch):
        session = _FakeSession([])
        monkeypatch.setattr(tools, "get_research_service", lambda s: _FakeResearchService())
        payload = _build_payload(osis=" ", doc_id="doc-3")
        orig_resolver = tools._resolve_document_osis

        def patched_resolver(sess, doc_id):
            assert sess is session
            return orig_resolver(sess, doc_id)

        monkeypatch.setattr(tools, "_resolve_document_osis", patched_resolver)
        with pytest.raises(MCPToolError):
            tools.handle_note_write(session, payload)
