from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Iterator, Literal

import pytest
from fastapi.testclient import TestClient

from theo.services.api.app.main import app
from theo.application.facades.database import get_session
from theo.services.api.app.models.export import (
    DeliverableAsset,
    DeliverableManifest,
    DeliverablePackage,
    serialise_asset_content,
)
from theo.services.api.app.models.ai import SermonPrepRequest
from theo.services.api.app.routes.ai.workflows import exports as exports_module
from theo.services.api.app.routes.ai.workflows import guardrails as guardrails_module
from theo.services.api.app.ai.rag.guardrails import GuardrailError
from theo.services.api.app.ai.rag.models import RAGAnswer, RAGCitation


class _DummyAuditLogger:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def log(self, **payload: object) -> None:
        self.calls.append(payload)


def _build_package(
    kind: Literal["sermon", "transcript"],
    formats: list[Literal["markdown", "ndjson", "csv", "pdf"]],
) -> DeliverablePackage:
    manifest = DeliverableManifest(
        export_id="pkg",
        schema_version="1",
        generated_at=datetime.now(UTC),
        type=kind,
        filters={},
    )
    assets: list[DeliverableAsset] = []
    for fmt in formats:
        if fmt == "pdf":
            assets.append(
                DeliverableAsset(
                    format=fmt,
                    filename=f"{kind}.pdf",
                    media_type="application/pdf",
                    content=f"{kind}-{fmt}-content".encode("utf-8"),
                )
            )
        else:
            assets.append(
                DeliverableAsset(
                    format=fmt,
                    filename=f"{kind}.{fmt}",
                    media_type=f"text/{fmt}",
                    content=f"{kind}-{fmt}-content",
                )
            )
    return DeliverablePackage(manifest=manifest, assets=assets)


@pytest.fixture(scope="module")
def api_client() -> Iterator[TestClient]:
    def override_session():
        yield object()

    app.dependency_overrides[get_session] = override_session
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.parametrize("export_format", ["markdown", "ndjson", "csv", "pdf"])
def test_sermon_export_returns_serialised_asset(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch, export_format: str
) -> None:
    request_body = {"topic": "Hope", "osis": None, "filters": {}, "model": None}
    expected_filters = SermonPrepRequest(**request_body).filters.model_dump(
        exclude_none=True
    )
    monkeypatch.setattr(
        exports_module,
        "generate_sermon_prep_outline",
        lambda *_, **__: object(),
    )
    captured_filters: dict | None = None

    def _capture_filters(response, *, formats, filters=None):
        nonlocal captured_filters
        captured_filters = filters
        return _build_package("sermon", formats)

    monkeypatch.setattr(
        exports_module,
        "build_sermon_deliverable",
        _capture_filters,
    )
    response = api_client.post(
        f"/ai/sermon-prep/export?format={export_format}",
        json=request_body,
    )
    assert response.status_code == 200
    payload = response.json()
    expected_media = "application/pdf" if export_format == "pdf" else f"text/{export_format}"
    expected_content = serialise_asset_content(
        b"sermon-pdf-content" if export_format == "pdf" else f"sermon-{export_format}-content"
    )
    assert captured_filters == expected_filters
    assert payload == {
        "preset": f"sermon-{export_format}",
        "format": export_format,
        "filename": f"sermon.{export_format}",
        "media_type": expected_media,
        "content": expected_content,
    }


@pytest.mark.parametrize("export_format", ["markdown", "csv", "pdf"])
def test_transcript_export_returns_serialised_asset(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch, export_format: str
) -> None:
    monkeypatch.setattr(
        exports_module,
        "build_transcript_deliverable",
        lambda session, document_id, *, formats: _build_package("transcript", formats),
    )
    response = api_client.post(
        "/ai/transcript/export",
        json={"document_id": "doc-1", "format": export_format},
    )
    assert response.status_code == 200
    payload = response.json()
    expected_media = "application/pdf" if export_format == "pdf" else f"text/{export_format}"
    expected_content = serialise_asset_content(
        b"transcript-pdf-content"
        if export_format == "pdf"
        else f"transcript-{export_format}-content"
    )
    assert payload == {
        "preset": f"transcript-{export_format}",
        "format": export_format,
        "filename": f"transcript.{export_format}",
        "media_type": expected_media,
        "content": expected_content,
    }


def _build_stub_guardrail_answer() -> RAGAnswer:
    return RAGAnswer(
        summary="Guardrail refusal",
        citations=
        [
            RAGCitation(
                index=1,
                osis="John.1.1",
                anchor="John 1:1",
                passage_id="guardrail-passage",
                document_id="guardrail-document",
                snippet="Guardrail refusal snippet",
            )
        ],
        model_name="guardrail.refusal",
        model_output="Guardrail refusal",
        guardrail_profile={"status": "refused"},
    )


def test_sermon_export_guardrail_error_returns_guardrail_payload(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    request_body = {"topic": "Hope", "osis": None, "filters": {}, "model": None}
    guardrail_exc = GuardrailError("Blocked", metadata={"code": "unsafe"})

    monkeypatch.setattr(
        guardrails_module,
        "build_guardrail_refusal",
        lambda session, *, reason=None: _build_stub_guardrail_answer(),
    )

    def _raise_guardrail(*_, **__):
        raise guardrail_exc

    monkeypatch.setattr(
        exports_module,
        "generate_sermon_prep_outline",
        _raise_guardrail,
    )

    expected_response = exports_module.guardrail_http_exception(
        guardrail_exc,
        session=object(),
        question=None,
        osis=request_body["osis"],
        filters=SermonPrepRequest(**request_body).filters,
    )
    expected_payload = json.loads(expected_response.body.decode("utf-8"))

    response = api_client.post(
        "/ai/sermon-prep/export",
        params={"format": "markdown"},
        json=request_body,
    )

    assert response.status_code == expected_response.status_code == 422
    assert response.json() == expected_payload
    assert (
        response.headers["X-Guardrail-Advisory"]
        == expected_response.headers["X-Guardrail-Advisory"]
    )


@pytest.mark.parametrize(
    "path, payload, expected_code",
    [
        (
            "/ai/sermon-prep/export",
            {"topic": "Hope", "osis": None, "filters": {}, "model": None},
            "AI_EXPORT_UNSUPPORTED_SERMON_FORMAT",
        ),
        (
            "/ai/transcript/export",
            {"document_id": "doc-1", "format": "docx"},
            "AI_EXPORT_UNSUPPORTED_TRANSCRIPT_FORMAT",
        ),
    ],
)
def test_export_routes_reject_unsupported_formats(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch, path: str, payload: dict, expected_code: str
) -> None:
    monkeypatch.setattr(
        exports_module,
        "generate_sermon_prep_outline",
        lambda *_, **__: object(),
    )

    monkeypatch.setattr(
        exports_module,
        "build_sermon_deliverable",
        lambda *_, **__: _build_package("sermon", ["markdown"]),
    )

    monkeypatch.setattr(
        exports_module,
        "build_transcript_deliverable",
        lambda *_, **__: _build_package("transcript", ["markdown"]),
    )

    params = {"format": "docx"} if path.endswith("sermon-prep/export") else None
    response = api_client.post(path, params=params, json=payload)

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == expected_code
    assert body["detail"] == body["error"]["message"]


def test_transcript_export_guardrail_error_logs_and_returns_ai_error(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    dummy_logger = _DummyAuditLogger()

    monkeypatch.setattr(
        exports_module.AuditLogWriter,
        "from_session",
        classmethod(lambda cls, session: dummy_logger),
    )

    guardrail_exc = GuardrailError("Transcript blocked")

    def _raise_guardrail(*_, **__):
        raise guardrail_exc

    monkeypatch.setattr(
        exports_module,
        "build_transcript_deliverable",
        _raise_guardrail,
    )

    response = api_client.post(
        "/ai/transcript/export",
        json={"document_id": "doc-1", "format": "pdf"},
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "AI_EXPORT_GUARDRAIL_BLOCKED"
    assert payload["error"]["message"] == str(guardrail_exc)
    assert payload["error"]["data"] == {"document_id": "doc-1", "format": "pdf"}
    assert dummy_logger.calls


def test_transcript_export_value_error_returns_ai_error(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    dummy_logger = _DummyAuditLogger()

    monkeypatch.setattr(
        exports_module.AuditLogWriter,
        "from_session",
        classmethod(lambda cls, session: dummy_logger),
    )

    def _raise_value_error(*_, **__):
        raise ValueError("bad request")

    monkeypatch.setattr(
        exports_module,
        "build_transcript_deliverable",
        _raise_value_error,
    )

    response = api_client.post(
        "/ai/transcript/export",
        json={"document_id": "doc-2", "format": "markdown"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "AI_EXPORT_INVALID_REQUEST"
    assert payload["error"]["message"] == "bad request"
    assert payload["error"]["data"] == {"document_id": "doc-2", "format": "markdown"}
    assert not dummy_logger.calls
