import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.main import app  # noqa: E402


def test_dss_links_endpoint_returns_matches() -> None:
    with TestClient(app) as client:
        response = client.get("/research/dss-links", params={"osis": "John.1.1"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["osis"] == "John.1.1"
        assert payload["total"] >= 1
        assert payload["links"], "Expected at least one DSS link"
        first = payload["links"][0]
        assert first["title"]
        assert first["url"].startswith("http")


def test_dss_links_endpoint_handles_ranges() -> None:
    with TestClient(app) as client:
        response = client.get("/research/dss-links", params={"osis": "Luke.2.1-Luke.2.3"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["osis"] == "Luke.2.1-Luke.2.3"
        assert payload["total"] >= 1
        osis_values = {link["osis"] for link in payload["links"]}
        assert "Luke.2.2" in osis_values
