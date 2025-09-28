from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Generator

import pytest
import schemathesis
from schemathesis import experimental
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import tomllib

from theo.services.api.app.core.database import Base, get_session
from theo.services.api.app.db.models import Document, Passage
from theo.services.api.app.main import app

CONFIG_PATH = PROJECT_ROOT / "contracts" / "schemathesis.toml"
CONFIG = tomllib.loads(CONFIG_PATH.read_text())
ENDPOINTS = CONFIG.get("endpoints", [])

experimental.OPEN_API_3_1.enable()


@pytest.fixture()
def schemathesis_schema() -> Generator[schemathesis.schemas.BaseSchema, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        document = Document(
            id="doc-1",
            title="Sample Document",
            source_type="article",
            collection="Test",
            authors=["Jane Doe"],
            doi="10.1234/example",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        passage = Passage(
            id="passage-1",
            document_id="doc-1",
            text="In the beginning was the Word.",
            osis_ref="John.1.1",
            page_no=1,
            start_char=0,
            end_char=32,
        )
        session.add(document)
        session.add(passage)
        session.commit()

    def _override_session() -> Generator[Session, None, None]:
        db_session = TestingSession()
        try:
            yield db_session
        finally:
            db_session.close()

    app.dependency_overrides[get_session] = _override_session

    with TestClient(app) as client:
        response = client.post(
            "/ai/llm",
            json={
                "name": "echo",
                "provider": "echo",
                "model": "echo",
                "make_default": True,
            },
        )
        assert response.status_code == 200, response.text

    schema = schemathesis.from_asgi("/openapi.json", app)
    try:
        yield schema
    finally:
        app.dependency_overrides.pop(get_session, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _build_request_body(path: str) -> dict[str, object]:
    if path == "/ai/citations/export":
        return {
            "citations": [
                {
                    "index": 1,
                    "osis": "John.1.1",
                    "anchor": "John 1:1",
                    "passage_id": "passage-1",
                    "document_id": "doc-1",
                    "document_title": "Sample Document",
                    "snippet": "In the beginning was the Word.",
                    "source_url": None,
                }
            ]
        }
    if path == "/ai/verse":
        return {
            "osis": "John.1.1",
            "question": "What is said?",
            "model": "echo",
        }
    if path == "/ai/sermon-prep":
        return {
            "topic": "Hope in John 1",
            "osis": "John.1.1",
            "model": "echo",
        }
    raise ValueError(f"Unsupported contract path: {path}")


@pytest.mark.parametrize(
    "endpoint",
    ENDPOINTS,
    ids=lambda item: f"{item['method']} {item['path']}",
)
def test_ai_contracts(endpoint: dict[str, str], schemathesis_schema: schemathesis.schemas.BaseSchema) -> None:
    method = endpoint["method"].upper()
    path = endpoint["path"]
    schema_endpoint = schemathesis_schema[path][method]
    case = schema_endpoint.make_case(body=_build_request_body(path))
    response = case.call_asgi()
    case.validate_response(response)
