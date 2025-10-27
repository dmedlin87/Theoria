from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from theo.infrastructure.api.app.ai.reasoning.perspectives import (
    PerspectiveCitation,
    PerspectiveSynthesis,
    PerspectiveView,
)
from theo.infrastructure.api.app.main import app


def test_perspectives_route_serialises_views(
    monkeypatch: pytest.MonkeyPatch, api_engine
) -> None:
    called: dict[str, object] = {}

    stub_view = PerspectiveView(
        perspective="skeptical",
        answer="Skeptical summary",
        confidence=0.42,
        key_claims=["Shared insight.", "Unique challenge."],
        citations=[
            PerspectiveCitation(
                document_id="doc-1",
                document_title="Skeptical Source",
                osis="John.20.1",
                snippet="Shared insight.",
                rank=1,
                score=0.8,
            )
        ],
    )

    stub_synthesis = PerspectiveSynthesis(
        consensus_points=["Shared insight."],
        tension_map={"skeptical": ["Unique challenge."]},
        meta_analysis="Shared insight. Skeptical focus: Unique challenge.",
        perspective_views={"skeptical": stub_view},
    )

    def _fake_synthesise(question, session, *, retrieval_service, base_filters=None, top_k=5):
        called.update(
            question=question,
            top_k=top_k,
            filters=base_filters,
            retrieval_service=retrieval_service,
        )
        return stub_synthesis

    monkeypatch.setattr(
        "theo.infrastructure.api.app.routes.ai.workflows.perspectives.synthesize_perspectives",
        _fake_synthesise,
    )

    with TestClient(app) as client:
        response = client.post(
            "/ai/perspectives",
            json={"question": "Where is hope?", "top_k": 4},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["question"] == "Where is hope?"
    assert payload["consensus_points"] == ["Shared insight."]
    assert payload["tension_map"] == {"skeptical": ["Unique challenge."]}
    assert payload["meta_analysis"].startswith("Shared insight")
    view = payload["perspective_views"]["skeptical"]
    assert view["answer"] == "Skeptical summary"
    assert pytest.approx(view["confidence"], rel=1e-3) == 0.42
    assert view["key_claims"] == ["Shared insight.", "Unique challenge."]
    assert view["citations"][0]["document_id"] == "doc-1"

    assert called["question"] == "Where is hope?"
    assert called["top_k"] == 4
    assert called["retrieval_service"] is not None
