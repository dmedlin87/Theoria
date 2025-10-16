from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from theo.application.facades.database import get_session
from theo.services.api.app.main import app
from theo.services.api.app.routes import export as export_route
from theo.services.api.app.models.search import HybridSearchRequest


def _override_session():
    yield object()


@pytest.mark.parametrize(
    ("requested_k", "limit_value"),
    [
        (50, 10),
        (25, 40),
    ],
)
def test_export_search_honours_limit_when_overfetching(
    monkeypatch: pytest.MonkeyPatch, requested_k: int, limit_value: int
) -> None:
    """Ensure the search export request caps ``k`` at ``min(k, limit + 1)`` when a limit is supplied."""

    captured: dict[str, HybridSearchRequest] = {}

    def fake_export_search_results(session, request):
        captured["request"] = request
        return object()

    monkeypatch.setattr(export_route, "export_search_results", fake_export_search_results)
    monkeypatch.setattr(
        export_route,
        "build_search_export",
        lambda payload, *, include_text, fields: ({}, []),
    )
    monkeypatch.setattr(
        export_route,
        "render_bundle",
        lambda manifest, records, output_format: ("{}", "application/json"),
    )

    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            response = client.get(
                "/export/search",
                params={"q": "hope", "k": requested_k, "limit": limit_value},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert "request" in captured
    request = captured["request"]
    assert isinstance(request, HybridSearchRequest)
    assert request.k == min(requested_k, limit_value + 1)
    assert request.limit == limit_value
