from __future__ import annotations

from typing import Iterable
import importlib

import pytest
from fastapi.testclient import TestClient

from mcp_server.server import TOOLS, app, _collect_schemas, _schema_ref


@pytest.fixture()
def client() -> Iterable[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_metadata_includes_tool_schemas(client: TestClient) -> None:
    response = client.get("/metadata")
    assert response.status_code == 200

    payload = response.json()
    assert payload["name"] == "theo-mcp-server"
    assert payload["version"] == "0.1.0"

    # Ensure every tool entry references the generated schema IDs.
    for tool in TOOLS:
        expected_request_ref = _schema_ref(tool.name, "request")
        expected_response_ref = _schema_ref(tool.name, "response")

        entry = next(item for item in payload["tools"] if item["name"] == tool.name)
        assert entry["input_schema"] == {"$ref": expected_request_ref}
        assert entry["output_schema"] == {"$ref": expected_response_ref}

    # Schemas payload should align with the helper used by metadata().
    assert payload["schemas"] == _collect_schemas(TOOLS)


def test_metadata_schema_base_url_can_be_overridden(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MCP_SCHEMA_BASE_URL", "https://staging.theo.local/mcp")

    response = client.get("/metadata")
    assert response.status_code == 200

    payload = response.json()
    for tool in TOOLS:
        expected_request_ref = _schema_ref(tool.name, "request")
        expected_response_ref = _schema_ref(tool.name, "response")
        entry = next(item for item in payload["tools"] if item["name"] == tool.name)
        assert entry["input_schema"]["$ref"].startswith(
            "https://staging.theo.local/mcp/"
        )
        assert entry["output_schema"]["$ref"].startswith(
            "https://staging.theo.local/mcp/"
        )
        assert entry["input_schema"] == {"$ref": expected_request_ref}
        assert entry["output_schema"] == {"$ref": expected_response_ref}

    # Ensure the schemas map uses the overridden base URL as well.
    for schema_id in payload["schemas"].keys():
        assert schema_id.startswith("https://staging.theo.local/mcp/")


def test_tools_disabled_without_feature_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    import mcp_server.server as server

    monkeypatch.delenv("MCP_TOOLS_ENABLED", raising=False)
    importlib.reload(server)

    with TestClient(server.app) as test_client:
        response = test_client.get("/metadata")
        assert response.status_code == 200
        payload = response.json()
        assert payload["tools"] == []
        assert payload["schemas"] == {}

    monkeypatch.setenv("MCP_TOOLS_ENABLED", "1")
    importlib.reload(server)

