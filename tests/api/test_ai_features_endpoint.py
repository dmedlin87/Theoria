import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.main import app  # noqa: E402


def test_ai_features_exposes_guardrail_catalogues(api_database) -> None:
    with TestClient(app) as client:
        response = client.get("/ai/features")
        assert response.status_code == 200
        payload = response.json()
        guardrails = payload.get("guardrails")
        assert guardrails is not None
        traditions = guardrails.get("theological_traditions")
        domains = guardrails.get("topic_domains")
        assert isinstance(traditions, list) and traditions, "traditions should be enumerated"
        assert isinstance(domains, list) and domains, "topic domains should be enumerated"
        assert all("slug" in item and "label" in item for item in traditions)
        assert all("slug" in item and "label" in item for item in domains)
