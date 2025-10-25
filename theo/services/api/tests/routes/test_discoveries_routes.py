"""Integration tests for discoveries and ingest routes."""

from __future__ import annotations

import importlib
import sys
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any, Generator
from unittest.mock import MagicMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from pydantic import field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from theo.adapters.persistence.models import Discovery, Document
from theo.application.facades.database import get_engine
from theo.services.api.app.main import app
from theo.services.api.app.adapters.security import require_principal
from theo.services.api.app.services.ingestion_service import get_ingestion_service

# ---------------------------------------------------------------------------
# Ensure the real discovery service is used for the duration of these tests.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def _use_real_discovery_service() -> Generator[None, None, None]:
    monkeypatcher = pytest.MonkeyPatch()
    stubbed_modules: dict[str, Any] = {}
    for module_name in (
        "theo.services.api.app.discoveries",
        "theo.services.api.app.discoveries.tasks",
    ):
        stubbed_modules[module_name] = sys.modules.pop(module_name, None)

    discoveries_module = importlib.import_module("theo.services.api.app.discoveries")
    real_service = discoveries_module.DiscoveryService
    routes_module = importlib.import_module("theo.services.api.app.routes.discoveries")

    class _CoercingDiscoveryResponse(routes_module.DiscoveryResponse):  # type: ignore[misc]
        @field_validator("id", mode="before")
        @classmethod
        def _ensure_string(cls, value: Any) -> str | None:
            if value is None:
                return None
            return str(value)

    monkeypatcher.setattr(routes_module, "DiscoveryService", real_service)
    monkeypatcher.setattr(routes_module, "DiscoveryResponse", _CoercingDiscoveryResponse)

    try:
        yield
    finally:
        monkeypatcher.undo()
        for name, module in stubbed_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


@pytest.fixture()
def discovery_records() -> Generator[dict[str, list[dict[str, Any]]], None, None]:
    engine = get_engine()
    now = datetime.now(UTC)
    with Session(engine) as session:
        session.execute(delete(Discovery))
        session.commit()

        user_entries: list[dict[str, Any]] = []
        samples = [
            {
                "type": "pattern",
                "viewed": False,
                "reaction": None,
                "confidence": 0.9,
                "relevance": 0.75,
                "created_at": now - timedelta(minutes=3),
            },
            {
                "type": "trend",
                "viewed": True,
                "reaction": "helpful",
                "confidence": 0.6,
                "relevance": 0.55,
                "created_at": now - timedelta(minutes=2),
            },
            {
                "type": "gap",
                "viewed": False,
                "reaction": None,
                "confidence": 0.3,
                "relevance": 0.45,
                "created_at": now - timedelta(minutes=1),
            },
        ]

        for index, sample in enumerate(samples, start=1):
            record = Discovery(
                user_id="test",
                discovery_type=sample["type"],
                title=f"Discovery {index}",
                description=f"Insight {index}",
                confidence=sample["confidence"],
                relevance_score=sample["relevance"],
                viewed=sample["viewed"],
                user_reaction=sample["reaction"],
                created_at=sample["created_at"],
                meta={"seed": index},
            )
            session.add(record)
            session.flush()
            user_entries.append(
                {
                    "id": record.id,
                    "type": sample["type"],
                    "viewed": sample["viewed"],
                    "reaction": sample["reaction"],
                    "confidence": sample["confidence"],
                    "created_at": sample["created_at"],
                }
            )

        other_record = Discovery(
            user_id="other-user",
            discovery_type="connection",
            title="Other Discovery",
            description="Not for the test user",
            confidence=0.8,
            relevance_score=0.5,
            viewed=False,
            user_reaction=None,
            created_at=now - timedelta(minutes=4),
            meta={"seed": "other"},
        )
        session.add(other_record)
        session.commit()
        other_entry = {
            "id": other_record.id,
            "type": other_record.discovery_type,
            "viewed": other_record.viewed,
        }

    try:
        yield {"user": user_entries, "other": [other_entry]}
    finally:
        with Session(engine) as cleanup:
            cleanup.execute(delete(Discovery))
            cleanup.commit()


class _StubIngestionService:
    def __init__(self) -> None:
        self.run_file_pipeline = self._run_file_pipeline
        self.run_url_pipeline = self._run_url_pipeline
        self.run_transcript_pipeline = self._run_transcript_pipeline

    def _create_document(
        self,
        session: Session,
        *,
        title: str,
        source_type: str,
        source_url: str | None = None,
    ) -> Document:
        document = Document(title=title, source_type=source_type, source_url=source_url)
        session.add(document)
        session.commit()
        session.refresh(document)
        return document

    def _run_file_pipeline(
        self,
        session: Session,
        source_path,
        frontmatter,
        dependencies=None,
    ) -> Document:
        return self._create_document(
            session, title="Stub Upload", source_type="file"
        )

    def ingest_file(self, session: Session, source_path, frontmatter):
        return self.run_file_pipeline(session, source_path, frontmatter)

    def _run_url_pipeline(
        self,
        session: Session,
        url: str,
        *,
        source_type: str | None = None,
        frontmatter=None,
        dependencies=None,
    ) -> Document:
        return self._create_document(
            session,
            title="Stub URL",
            source_type=source_type or "url",
            source_url=url,
        )

    def ingest_url(
        self,
        session: Session,
        url: str,
        *,
        source_type: str | None = None,
        frontmatter=None,
    ) -> Document:
        return self.run_url_pipeline(
            session,
            url,
            source_type=source_type,
            frontmatter=frontmatter,
        )

    def _run_transcript_pipeline(
        self,
        session: Session,
        transcript_path,
        *,
        frontmatter=None,
        audio_path=None,
        transcript_filename=None,
        audio_filename=None,
        dependencies=None,
    ) -> Document:
        return self._create_document(
            session, title="Stub Transcript", source_type="transcript"
        )

    def ingest_transcript(
        self,
        session: Session,
        transcript_path,
        *,
        frontmatter=None,
        audio_path=None,
        transcript_filename=None,
        audio_filename=None,
    ) -> Document:
        return self.run_transcript_pipeline(
            session,
            transcript_path,
            frontmatter=frontmatter,
            audio_path=audio_path,
            transcript_filename=transcript_filename,
            audio_filename=audio_filename,
        )


@pytest.fixture()
def stub_ingestion_service() -> Generator[_StubIngestionService, None, None]:
    service = _StubIngestionService()
    app.dependency_overrides[get_ingestion_service] = lambda: service
    try:
        yield service
    finally:
        app.dependency_overrides.pop(get_ingestion_service, None)
        engine = get_engine()
        with Session(engine) as session:
            session.execute(delete(Document))
            session.commit()


@pytest.fixture()
def schedule_refresh_mock(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock()

    def _conditional_schedule(background_tasks, user_id):
        if user_id:
            mock(background_tasks, user_id)

    monkeypatch.setattr(
        "theo.services.api.app.routes.ingest.schedule_discovery_refresh",
        _conditional_schedule,
    )
    return mock


def _count_discoveries(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Discovery)) or 0


def test_list_discoveries_returns_stats_and_supports_filters(
    discovery_records: dict[str, list[dict[str, Any]]]
) -> None:
    with TestClient(app) as client:
        response = client.get("/discoveries")
    assert response.status_code == 200
    payload = response.json()
    expected_total = len(discovery_records["user"])
    assert len(payload["discoveries"]) == expected_total

    ordered = sorted(
        discovery_records["user"], key=lambda item: item["created_at"], reverse=True
    )
    assert [entry["id"] for entry in payload["discoveries"]] == [
        str(item["id"]) for item in ordered
    ]

    expected_stats = {
        "total": expected_total,
        "unviewed": sum(1 for item in discovery_records["user"] if not item["viewed"]),
        "byType": {
            sample["type"]: sum(
                1 for item in discovery_records["user"] if item["type"] == sample["type"]
            )
            for sample in discovery_records["user"]
        },
        "averageConfidence": round(
            sum(item["confidence"] for item in discovery_records["user"]) / expected_total,
            4,
        ),
    }
    assert payload["stats"] == expected_stats

    with Session(get_engine()) as session:
        assert _count_discoveries(session) == expected_total + len(
            discovery_records["other"]
        )

    filtered_type = discovery_records["user"][0]["type"]
    with TestClient(app) as client:
        type_response = client.get("/discoveries", params={"discovery_type": filtered_type})
    assert type_response.status_code == 200
    type_payload = type_response.json()
    assert {
        item.get("type") or item.get("discovery_type")
        for item in type_payload["discoveries"]
    } == {filtered_type}
    with Session(get_engine()) as session:
        assert _count_discoveries(session) == expected_total + len(
            discovery_records["other"]
        )

    with TestClient(app) as client:
        viewed_response = client.get("/discoveries", params={"viewed": False})
    assert viewed_response.status_code == 200
    viewed_payload = viewed_response.json()
    assert all(not item["viewed"] for item in viewed_payload["discoveries"])
    with Session(get_engine()) as session:
        assert _count_discoveries(session) == expected_total + len(
            discovery_records["other"]
        )


def test_discovery_mutations_update_records(discovery_records) -> None:
    unviewed = next(item for item in discovery_records["user"] if not item["viewed"])
    other_id = discovery_records["other"][0]["id"]

    with TestClient(app) as client:
        mark_response = client.post(f"/discoveries/{unviewed['id']}/view")
    assert mark_response.status_code == 204
    with Session(get_engine()) as session:
        refreshed = session.get(Discovery, unviewed["id"])
        assert refreshed is not None
        assert refreshed.viewed is True

    with TestClient(app) as client:
        foreign_mark = client.post(f"/discoveries/{other_id}/view")
    assert foreign_mark.status_code == 404

    target = discovery_records["user"][0]
    with TestClient(app) as client:
        feedback_response = client.post(
            f"/discoveries/{target['id']}/feedback", json={"helpful": False}
        )
    assert feedback_response.status_code == 204
    with Session(get_engine()) as session:
        refreshed = session.get(Discovery, target["id"])
        assert refreshed is not None
        assert refreshed.user_reaction == "not_helpful"

    with TestClient(app) as client:
        feedback_other = client.post(
            f"/discoveries/{other_id}/feedback", json={"helpful": True}
        )
    assert feedback_other.status_code == 404

    dismiss_target = discovery_records["user"][1]
    with TestClient(app) as client:
        dismiss_response = client.delete(f"/discoveries/{dismiss_target['id']}")
    assert dismiss_response.status_code == 204
    with Session(get_engine()) as session:
        refreshed = session.get(Discovery, dismiss_target["id"])
        assert refreshed is not None
        assert refreshed.viewed is True
        assert refreshed.user_reaction == "dismissed"

    with TestClient(app) as client:
        dismiss_other = client.delete(f"/discoveries/{other_id}")
    assert dismiss_other.status_code == 404


@pytest.mark.no_auth_override
def test_discoveries_require_authentication() -> None:
    def _principal_without_subject(request: Request):
        principal = {"method": "override", "subject": None}
        request.state.principal = principal
        return principal

    app.dependency_overrides[require_principal] = _principal_without_subject
    try:
        with TestClient(app) as client:
            response = client.get("/discoveries")
    finally:
        app.dependency_overrides.pop(require_principal, None)
    assert response.status_code == 403


def test_ingest_file_schedules_refresh(
    stub_ingestion_service: _StubIngestionService,
    schedule_refresh_mock: MagicMock,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/ingest/file",
            files={"file": ("sample.txt", BytesIO(b"hello world"), "text/plain")},
        )
    assert response.status_code == 200
    payload = response.json()
    assert schedule_refresh_mock.call_count == 1
    args, _ = schedule_refresh_mock.call_args
    assert args[1] == "test"

    document_id = payload["document_id"]
    with Session(get_engine()) as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.source_type == "file"

    with Session(get_engine()) as session:
        session.execute(delete(Document).where(Document.id == document_id))
        session.commit()


def test_ingest_url_schedules_refresh_and_handles_missing_user(
    stub_ingestion_service: _StubIngestionService,
    schedule_refresh_mock: MagicMock,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/ingest/url",
            json={"url": "https://example.com/resource", "source_type": "web_page"},
        )
    assert response.status_code == 200
    document_id = response.json()["document_id"]
    assert schedule_refresh_mock.call_count == 1
    args, _ = schedule_refresh_mock.call_args
    assert args[1] == "test"

    with Session(get_engine()) as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.source_url == "https://example.com/resource"

    schedule_refresh_mock.reset_mock()

    def _anonymous_principal(request: Request):
        request.state.principal = {}
        return {}

    app.dependency_overrides[require_principal] = _anonymous_principal
    try:
        with TestClient(app) as client:
            anonymous_response = client.post(
                "/ingest/url",
                json={"url": "https://example.com/anonymous", "source_type": "web_page"},
            )
        assert anonymous_response.status_code == 200, anonymous_response.text
    finally:
        app.dependency_overrides.pop(require_principal, None)

    assert schedule_refresh_mock.call_count == 0

    anon_document_id = anonymous_response.json()["document_id"]
    with Session(get_engine()) as session:
        document = session.get(Document, anon_document_id)
        assert document is not None
        assert document.source_url == "https://example.com/anonymous"

    with Session(get_engine()) as session:
        session.execute(
            delete(Document).where(
                Document.id.in_([document_id, anon_document_id])
            )
        )
        session.commit()


def test_ingest_transcript_schedules_refresh(
    stub_ingestion_service: _StubIngestionService,
    schedule_refresh_mock: MagicMock,
) -> None:
    transcript_content = "WEBVTT\n\n00:00.000 --> 00:01.000\nHello world"
    with TestClient(app) as client:
        response = client.post(
            "/ingest/transcript",
            files={
                "transcript": (
                    "session.vtt",
                    BytesIO(transcript_content.encode()),
                    "text/vtt",
                ),
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert schedule_refresh_mock.call_count == 1
    args, _ = schedule_refresh_mock.call_args
    assert args[1] == "test"

    document_id = payload["document_id"]
    with Session(get_engine()) as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.source_type == "transcript"

    with Session(get_engine()) as session:
        session.execute(delete(Document).where(Document.id == document_id))
        session.commit()
