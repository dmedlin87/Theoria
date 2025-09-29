"""Contract tests ensuring OpenAPI schema coverage via Schemathesis."""
import os
import sys
from pathlib import Path
import tomllib

import pytest
import schemathesis
from schemathesis import openapi as schemathesis_openapi
from fastapi import Request as FastAPIRequest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from schemathesis.schemas import BaseSchema

os.environ.setdefault("THEO_DISABLE_AI_SETTINGS", "1")
os.environ.setdefault("THEO_AUTH_ALLOW_ANONYMOUS", "1")
os.environ.setdefault("SETTINGS_SECRET_KEY", "contract-test-secret")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.ai.registry import (  # noqa: E402
    LLMModel,
    LLMRegistry,
    save_llm_registry,
)
from theo.services.api.app.core.database import (  # noqa: E402
    Base,
    configure_engine,
    get_engine,
    get_session,
)
from theo.services.api.app.main import app  # noqa: E402
from theo.services.api.app.security import require_principal  # noqa: E402

CONFIG_PATH = PROJECT_ROOT / "contracts" / "schemathesis.toml"
with CONFIG_PATH.open("rb") as config_file:
    CONTRACT_CONFIG = tomllib.load(config_file)

ENDPOINT_CASES: list[tuple[str, str, str]] = []
for suite in CONTRACT_CONFIG.get("suites", []):
    suite_name = suite.get("name", "suite")
    for endpoint in suite.get("endpoints", []):
        method = str(endpoint.get("method", "GET")).upper()
        path = str(endpoint.get("path"))
        if path:
            ENDPOINT_CASES.append((suite_name, method, path))

ENDPOINT_IDS = [f"{suite}:{method} {path}" for suite, method, path in ENDPOINT_CASES]


@pytest.fixture(scope="session")
def contract_engine(tmp_path_factory: pytest.TempPathFactory):
    db_path = tmp_path_factory.mktemp("contracts") / "contract.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        registry = LLMRegistry()
        registry.add_model(LLMModel(name="echo", provider="echo", model="echo"), make_default=True)
        save_llm_registry(session, registry)
        session.commit()
    return engine


@pytest.fixture(scope="session")
def contract_client(contract_engine) -> TestClient:
    def _override_session():
        database = Session(contract_engine)
        try:
            yield database
        finally:
            database.close()

    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture(autouse=True)
def _override_authentication():
    def _principal_override(fastapi_request: FastAPIRequest):
        principal = {"method": "override", "subject": "contract-test"}
        fastapi_request.state.principal = principal
        return principal

    app.dependency_overrides[require_principal] = _principal_override
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_principal, None)


@pytest.fixture(scope="session")
def openapi_schema(contract_client: TestClient):
    return schemathesis_openapi.from_asgi("/openapi.json", app)


@pytest.mark.parametrize("_suite, method, path", ENDPOINT_CASES, ids=ENDPOINT_IDS)
def test_contract_endpoints(
    _suite: str,
    method: str,
    path: str,
    openapi_schema: BaseSchema,
    contract_client: TestClient,
) -> None:
    operation = openapi_schema.get(path, method).get(method)
    case = openapi_schema.make_case(operation=operation)
    case.call_and_validate(
        session=contract_client,
        checks=(schemathesis.checks.not_a_server_error,),
    )
