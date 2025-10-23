from fastapi.testclient import TestClient


def test_dss_links_endpoint_returns_matches(
    api_test_client: TestClient,
) -> None:
    response = api_test_client.get(
        "/research/dss-links", params={"osis": "John.1.1"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["osis"] == "John.1.1"
    assert payload["total"] >= 1
    assert payload["links"], "Expected at least one DSS link"
    first = payload["links"][0]
    assert first["title"]
    assert first["url"].startswith("http")


def test_dss_links_endpoint_handles_ranges(
    api_test_client: TestClient,
) -> None:
    response = api_test_client.get(
        "/research/dss-links", params={"osis": "Luke.2.1-Luke.2.3"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["osis"] == "Luke.2.1-Luke.2.3"
    assert payload["total"] >= 1
    osis_values = {link["osis"] for link in payload["links"]}
    assert "Luke.2.2" in osis_values


def test_dss_links_endpoint_handles_missing_osis(
    api_test_client: TestClient,
) -> None:
    response = api_test_client.get(
        "/research/dss-links", params={"osis": "Nonexistent.1.1"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["osis"] == "Nonexistent.1.1"
    assert payload["total"] == 0
    assert payload["links"] == []


def test_dss_links_endpoint_ignores_malformed_records(
    api_test_client: TestClient, monkeypatch
) -> None:
    from theo.domain.research import dss_links as module

    def fake_dataset() -> dict[str, list[dict[str, str]]]:
        return {
            "John.1.1": [
                {"url": "https://example.org/without-id", "fragment": "4Q246"},
                {"id": "missing-url", "title": "Should be skipped"},
            ]
        }

    monkeypatch.setattr(module, "dss_links_dataset", fake_dataset)

    response = api_test_client.get(
        "/research/dss-links", params={"osis": "John.1.1"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["links"][0]["id"].startswith("John.1.1:")
    assert payload["links"][0]["url"] == "https://example.org/without-id"
