from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterator, Literal

import pytest
from fastapi.testclient import TestClient

from theo.services.api.app.main import app
from theo.services.api.app.core.database import get_session
from theo.services.api.app.models.export import (
    DeliverableAsset,
    DeliverableManifest,
    DeliverablePackage,
)
from theo.services.api.app.routes.ai import workflows as workflows_module


def _build_package(
    kind: Literal["sermon", "transcript"],
    formats: list[Literal["markdown", "ndjson", "csv"]],
) -> DeliverablePackage:
    manifest = DeliverableManifest(
        export_id="pkg",
        schema_version="1",
        generated_at=datetime.now(UTC),
        type=kind,
        filters={},
    )
    assets = [
        DeliverableAsset(
            format=fmt,
            filename=f"{kind}.{fmt}",
            media_type=f"text/{fmt}",
            content=f"{kind}-{fmt}-content",
        )
        for fmt in formats
    ]
    return DeliverablePackage(manifest=manifest, assets=assets)


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    def override_session():
        yield object()

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.parametrize("export_format", ["markdown", "ndjson", "csv"])
def test_sermon_export_returns_serialised_asset(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch, export_format: str
) -> None:
    monkeypatch.setattr(
        workflows_module,
        "generate_sermon_prep_outline",
        lambda *_, **__: object(),
    )
    monkeypatch.setattr(
        workflows_module,
        "build_sermon_deliverable",
        lambda response, *, formats, filters=None: _build_package("sermon", formats),
    )
    response = api_client.post(
        f"/ai/sermon-prep/export?format={export_format}",
        json={"topic": "Hope", "osis": None, "filters": {}, "model": None},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "preset": f"sermon-{export_format}",
        "format": export_format,
        "filename": f"sermon.{export_format}",
        "media_type": f"text/{export_format}",
        "content": f"sermon-{export_format}-content",
    }


@pytest.mark.parametrize("export_format", ["markdown", "csv"])
def test_transcript_export_returns_serialised_asset(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch, export_format: str
) -> None:
    monkeypatch.setattr(
        workflows_module,
        "build_transcript_deliverable",
        lambda session, document_id, *, formats: _build_package("transcript", formats),
    )
    response = api_client.post(
        "/ai/transcript/export",
        json={"document_id": "doc-1", "format": export_format},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "preset": f"transcript-{export_format}",
        "format": export_format,
        "filename": f"transcript.{export_format}",
        "media_type": f"text/{export_format}",
        "content": f"transcript-{export_format}-content",
    }
