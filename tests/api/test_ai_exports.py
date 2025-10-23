from __future__ import annotations

import base64
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
)
from theo.services.api.app.models.ai import SermonPrepRequest
from theo.services.api.app.routes.ai.workflows import exports as exports_module


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
    expected_content = (
        base64.b64encode(b"sermon-pdf-content").decode("ascii")
        if export_format == "pdf"
        else f"sermon-{export_format}-content"
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
    expected_content = (
        base64.b64encode(b"transcript-pdf-content").decode("ascii")
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
