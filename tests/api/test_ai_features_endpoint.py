from fastapi.testclient import TestClient


def test_ai_features_exposes_guardrail_catalogues(
    api_test_client: TestClient,
) -> None:
    response = api_test_client.get("/ai/features")
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
