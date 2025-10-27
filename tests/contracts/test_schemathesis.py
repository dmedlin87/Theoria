"""Contract tests ensuring OpenAPI schema coverage via Schemathesis."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping
from uuid import uuid4
import tomllib

import pytest

pytestmark = pytest.mark.contract
import schemathesis
from schemathesis import openapi as schemathesis_openapi

try:  # pragma: no cover - compatibility with Schemathesis <4
    from schemathesis import experimental as schemathesis_experimental
except ImportError:  # pragma: no cover - Schemathesis 4+ removed experimental module
    schemathesis_experimental = None
from fastapi import Request as FastAPIRequest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from schemathesis.schemas import BaseSchema

from theo.adapters.persistence import models as persistence_models  # noqa: E402

from theo.infrastructure.api.app.analytics.topics import (  # noqa: E402
    TopicCluster,
    TopicDigest,
)
from theo.infrastructure.api.app.ai.rag import RAGAnswer  # noqa: E402
from theo.infrastructure.api.app.ai.trails import TrailReplayResult  # noqa: E402
from theo.infrastructure.api.app.models.ai import (  # noqa: E402
    ChatGoalState,
    ChatMemoryEntry,
    ChatSessionMessage,
    ChatSessionPreferences,
    ChatSessionResponse,
    ChatSessionState,
    CitationExportResponse,
    ExportDeliverableResponse,
)
from theo.infrastructure.api.app.models.trails import (  # noqa: E402
    TrailReplayDiff,
    TrailReplayResponse,
)
from theo.infrastructure.api.app.models.watchlists import (  # noqa: E402
    WatchlistResponse,
    WatchlistRunResponse,
)
from theo.infrastructure.api.app.models.research import (  # noqa: E402
    ResearchNote,
    ResearchNotesResponse,
)
from theo.infrastructure.api.app.models.search import (  # noqa: E402
    HybridSearchResponse,
    HybridSearchResult,
)
from theo.infrastructure.api.app.models.verses import (  # noqa: E402
    VerseTimelineBucket,
    VerseTimelineResponse,
)
from theo.infrastructure.api.app.models.documents import (  # noqa: E402
    DocumentListResponse,
    DocumentSummary,
)
from theo.application.facades.settings import get_settings  # noqa: E402

os.environ.setdefault("THEO_DISABLE_AI_SETTINGS", "1")
os.environ.setdefault("THEO_AUTH_ALLOW_ANONYMOUS", "1")
os.environ.setdefault("THEO_ALLOW_INSECURE_STARTUP", "1")
os.environ.setdefault("SETTINGS_SECRET_KEY", "contract-test-secret")
os.environ.setdefault("THEORIA_ENVIRONMENT", "development")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

pytest.importorskip("theo.adapters.persistence.models")

from theo.infrastructure.api.app.ai.registry import (  # noqa: E402
    LLMModel,
    LLMRegistry,
    save_llm_registry,
)
from theo.application.facades.database import (  # noqa: E402
    Base,
    configure_engine,
    get_engine,
    get_session,
)
from theo.infrastructure.api.app.main import app  # noqa: E402
from theo.infrastructure.api.app.adapters.security import require_principal  # noqa: E402

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


@dataclass(frozen=True)
class ContractTestContext:
    chat_session_id: str
    trail_id: str
    provider_name: str
    osis_ref: str


ValueProvider = Callable[[ContractTestContext], Any] | Any


@dataclass(frozen=True)
class CaseOverride:
    path_parameters: Mapping[str, ValueProvider] = field(default_factory=dict)
    query_parameters: Mapping[str, ValueProvider] = field(default_factory=dict)
    headers: Mapping[str, ValueProvider] = field(default_factory=dict)
    body: ValueProvider | None = None
    expected_status: int | None = None
    validate_response: bool = True


def _resolve_value(value: ValueProvider, context: ContractTestContext) -> Any:
    return value(context) if callable(value) else value


def _resolve_mapping(
    mapping: Mapping[str, ValueProvider], context: ContractTestContext
) -> dict[str, Any]:
    return {key: _resolve_value(value, context) for key, value in mapping.items()}


CASE_OVERRIDES: dict[tuple[str, str], CaseOverride] = {
    ("POST", "/ai/chat"): CaseOverride(
        body=lambda ctx: {
            "session_id": ctx.chat_session_id,
            "messages": [
                {"role": "user", "content": "Tell me about hope."},
            ],
            "model": "echo",
        },
        expected_status=200,
    ),
    ("GET", "/ai/chat/{session_id}"): CaseOverride(
        path_parameters={"session_id": lambda ctx: ctx.chat_session_id},
        expected_status=200,
        validate_response=False,
    ),
    ("POST", "/ai/citations/export"): CaseOverride(
        body=lambda ctx: {
            "citations": [
                {
                    "index": 0,
                    "osis": ctx.osis_ref,
                    "anchor": ctx.osis_ref,
                    "passage_id": "passage-contract",
                    "document_id": "doc-contract",
                    "document_title": "Sample Document",
                    "snippet": "For God so loved the world.",
                    "source_url": "https://example.com",
                    "raw_snippet": "For God so loved the world.",
                }
            ]
        },
        expected_status=200,
        validate_response=False,
    ),
    ("POST", "/ai/sermon-prep/export"): CaseOverride(
        body=lambda ctx: {
            "topic": "Hope",
            "osis": ctx.osis_ref,
            "model": "echo",
        },
        expected_status=200,
    ),
    ("GET", "/ai/digest"): CaseOverride(expected_status=200),
    ("POST", "/ai/digest/watchlists"): CaseOverride(
        body=lambda ctx: {
            "name": "Weekly Hope",
            "filters": {"osis": [ctx.osis_ref]},
            "cadence": "weekly",
        },
        expected_status=201,
    ),
    ("GET", "/ai/llm"): CaseOverride(expected_status=200),
    ("POST", "/analytics/feedback"): CaseOverride(
        body=lambda ctx: {
            "action": "thumbs_up",
            "user_id": "contract-user",
            "chat_session_id": ctx.chat_session_id,
            "score": 1,
            "confidence": 0.9,
        },
        expected_status=202,
    ),
    ("GET", "/documents/"): CaseOverride(expected_status=200),
    ("GET", "/research/notes"): CaseOverride(
        query_parameters={"osis": lambda ctx: ctx.osis_ref},
        expected_status=200,
    ),
    ("GET", "/search/"): CaseOverride(
        query_parameters={"q": lambda ctx: "hope"},
        expected_status=200,
    ),
    ("GET", "/verses/{osis}/timeline"): CaseOverride(
        path_parameters={"osis": lambda ctx: ctx.osis_ref},
        query_parameters={"window": "month", "limit": 3},
        expected_status=200,
    ),
    ("PUT", "/settings/ai/providers/{provider}"): CaseOverride(
        path_parameters={"provider": lambda ctx: ctx.provider_name},
        body={
            "api_key": "test-key",
            "default_model": "echo",
            "extra_headers": {"X-Test": "1"},
        },
        expected_status=200,
    ),
    ("POST", "/trails/{trail_id}/replay"): CaseOverride(
        path_parameters={"trail_id": lambda ctx: ctx.trail_id},
        body={"model": "echo"},
        expected_status=200,
    ),
}


@pytest.fixture(scope="session", autouse=True)
def _optimise_lifespan():
    patcher = pytest.MonkeyPatch()

    def _noop_migrations(*_args, **_kwargs):
        return []

    def _noop_seed(_session):
        return None

    patcher.setattr(
        "theo.infrastructure.api.app.db.run_sql_migrations.run_sql_migrations",
        _noop_migrations,
    )
    patcher.setattr(
        "theo.infrastructure.api.app.bootstrap.lifecycle.run_sql_migrations",
        _noop_migrations,
    )
    patcher.setattr(
        "theo.infrastructure.api.app.bootstrap.lifecycle.seed_reference_data",
        _noop_seed,
    )
    patcher.setattr(
        "theo.infrastructure.api.app.db.seeds.seed_reference_data",
        _noop_seed,
    )
    patcher.setattr(
        "theo.infrastructure.api.app.workers.discovery_scheduler.start_discovery_scheduler",
        lambda: None,
        raising=False,
    )
    patcher.setattr(
        "theo.infrastructure.api.app.workers.discovery_scheduler.stop_discovery_scheduler",
        lambda: None,
        raising=False,
    )

    try:
        yield
    finally:
        patcher.undo()


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
def contract_context(contract_engine) -> ContractTestContext:
    chat_session_id = "chat-session-contract"
    trail_id = "trail-contract"
    provider_name = "echo"
    osis_ref = "John 3:16"
    now = datetime.now(UTC)
    goal = ChatGoalState(
        id="goal-contract",
        title="Explore hope",
        trail_id=trail_id,
        status="active",
        priority=0,
        summary=None,
        created_at=now,
        updated_at=now,
        last_interaction_at=now,
    )
    memory_entry = ChatMemoryEntry(
        question="What is hope?",
        answer="Hope is confident expectation.",
        created_at=now,
        citations=[],
        document_ids=[],
        key_entities=[],
        recommended_actions=[],
    )
    preferences = ChatSessionPreferences(mode="standard")
    with Session(contract_engine) as session:
        trail = persistence_models.AgentTrail(
            id=trail_id,
            workflow="verse_copilot",
            status="completed",
            plan_md="Plan",
            final_md=None,
            input_payload={"osis": osis_ref},
            output_payload={"summary": "Initial output"},
            started_at=now,
            completed_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(trail)
        chat_session = persistence_models.ChatSession(
            id=chat_session_id,
            stance="neutral",
            summary="Initial summary",
            memory_snippets=[memory_entry.model_dump(mode="json")],
            document_ids=[],
            goals=[goal.model_dump(mode="json")],
            preferences=preferences.model_dump(mode="json"),
            created_at=now,
            updated_at=now,
            last_interaction_at=now,
        )
        session.add(chat_session)
        document = persistence_models.Document(
            id="doc-contract",
            title="Sample Document",
            source_type="sermon",
            collection="contract-suite",
            created_at=now,
            updated_at=now,
        )
        session.add(document)
        session.commit()
    return ContractTestContext(
        chat_session_id=chat_session_id,
        trail_id=trail_id,
        provider_name=provider_name,
        osis_ref=osis_ref,
    )


@pytest.fixture(scope="session", autouse=True)
def _stub_external_services(contract_context: ContractTestContext):
    patcher = pytest.MonkeyPatch()

    settings = get_settings()
    settings.intent_tagger_enabled = False
    settings.topic_digest_ttl_seconds = 60
    settings.verse_timeline_enabled = True

    def _fake_run_guarded_chat(
        _session,
        *,
        question: str,
        osis: str | None = None,
        filters=None,
        model_name: str | None = None,
        recorder=None,
        memory_context=None,
        mode: str | None = None,
    ) -> RAGAnswer:
        summary = f"Stubbed answer about {question.lower()}"
        return RAGAnswer(
            summary=summary,
            citations=[],
            model_name=model_name or "echo",
            model_output=summary,
            guardrail_profile=None,
            fallacy_warnings=[],
            critique=None,
            revision=None,
            reasoning_trace=None,
        )

    patcher.setattr(
        "theo.infrastructure.api.app.routes.ai.workflows.chat.run_guarded_chat",
        _fake_run_guarded_chat,
    )
    patcher.setattr(
        "theo.infrastructure.api.app.routes.ai.workflows.chat.ensure_completion_safe",
        lambda *_args, **_kwargs: None,
    )

    class _StubCitationManifest:
        def __init__(
            self,
            doc_count: int,
            data: dict[str, object] | None = None,
        ) -> None:
            base = {
                "schema_version": "1.0",
                "created_at": datetime.now(UTC).isoformat(),
                "type": "documents",
                "filters": {},
                "totals": {"documents": doc_count, "citations": doc_count},
                "export_id": "export-contract",
                "model_preset": "echo",
            }
            if data:
                base.update(data)
            self._data = base
            self.export_id = base["export_id"]
            self.model_preset = base.get("model_preset")
            self.schema_version = base["schema_version"]
            self.created_at = base["created_at"]
            self.type = base["type"]
            self.filters = base["filters"]
            self.totals = base["totals"]

        def model_copy(self, update: dict[str, object] | None = None):
            merged = dict(self._data)
            if update:
                merged.update(update)
            return _StubCitationManifest(
                doc_count=merged["totals"]["documents"],
                data=merged,
            )

        def model_dump(self, mode: str = "json") -> dict[str, object]:
            return dict(self._data) | {"mode": mode}

    def _fake_build_citation_export(
        document_details,
        *,
        style="csl-json",
        anchors=None,
        filters=None,
    ):
        manifest = _StubCitationManifest(doc_count=len(document_details))
        records = []
        csl_entries = []
        for detail in document_details:
            snippet = None
            if detail.passages:
                passage = detail.passages[0]
                meta = passage.meta or {}
                snippet = meta.get("snippet") or passage.text
            records.append(
                {
                    "document_id": detail.id,
                    "osis": contract_context.osis_ref,
                    "snippet": snippet or "Sample snippet",
                }
            )
            csl_entries.append(
                {
                    "id": detail.id,
                    "title": detail.title or "Sample Document",
                    "URL": "https://example.com",
                }
            )
        return manifest, records, csl_entries

    patcher.setattr(
        "theo.infrastructure.api.app.routes.ai.workflows.exports.build_citation_export",
        _fake_build_citation_export,
    )

    class _StubSermonAnswer:
        summary = "Outline summary"
        citations: list[dict[str, object]] = []

    class _StubAsset:
        format = "markdown"
        filename = "sermon.md"
        media_type = "text/markdown"

        def __init__(self) -> None:
            self.content = "# Sermon Outline\n- Hope\n"

    class _StubManifest:
        model_preset = "echo"

        def model_dump(self, mode: str = "json") -> dict[str, str]:
            return {"model_preset": self.model_preset, "mode": mode}

    class _StubPackage:
        def __init__(self) -> None:
            self.manifest = _StubManifest()

        def get_asset(self, _format: str) -> _StubAsset:
            return _StubAsset()

    def _fake_build_sermon_deliverable(*_args, **_kwargs):
        return _StubPackage()

    patcher.setattr(
        "theo.infrastructure.api.app.routes.ai.workflows.exports.build_sermon_deliverable",
        _fake_build_sermon_deliverable,
    )

    def _fake_generate_sermon_prep_outline(*_args, **_kwargs):
        response = type(
            "StubSermonResponse",
            (),
            {
                "answer": _StubSermonAnswer(),
                "manifest": _StubManifest(),
            },
        )
        return response()

    patcher.setattr(
        "theo.infrastructure.api.app.routes.ai.workflows.exports.generate_sermon_prep_outline",
        _fake_generate_sermon_prep_outline,
    )

    class _StubAuditLogger:
        def log(self, *_args, **_kwargs) -> None:
            return None

    def _fake_audit_from_session(_cls, _session):
        return _StubAuditLogger()

    patcher.setattr(
        "theo.infrastructure.api.app.ai.audit_logging.AuditLogWriter.from_session",
        classmethod(_fake_audit_from_session),
    )

    now = datetime.now(UTC)

    class _StubDigestService:
        def __init__(self, _session, ttl) -> None:
            self._digest = TopicDigest(
                generated_at=now,
                window_start=now,
                topics=[
                    TopicCluster(
                        topic="hope",
                        new_documents=1,
                        total_documents=5,
                        document_ids=["doc-contract"],
                    )
                ],
            )

        def ensure_latest(self) -> TopicDigest:
            return self._digest

    patcher.setattr(
        "theo.infrastructure.api.app.routes.ai.digest.DigestService",
        _StubDigestService,
    )

    class _StubWatchlistsService:
        def __init__(self, _session) -> None:
            self._now = now

        def create(self, user_id: str, payload) -> WatchlistResponse:
            return WatchlistResponse(
                id="watchlist-contract",
                user_id=user_id,
                name=payload.name,
                filters=payload.filters or {},
                cadence=payload.cadence or "weekly",
                delivery_channels=payload.delivery_channels or ["email"],
                is_active=payload.is_active if payload.is_active is not None else True,
                last_run=None,
                created_at=self._now,
                updated_at=self._now,
            )

    patcher.setattr(
        "theo.infrastructure.api.app.routes.ai.watchlists._service",
        lambda _session: _StubWatchlistsService(_session),
    )

    patcher.setattr(
        "theo.infrastructure.api.app.routes.analytics.record_feedback_from_payload",
        lambda _session, _payload: None,
    )

    def _fake_list_documents(_session, limit: int, offset: int) -> DocumentListResponse:
        summary = DocumentSummary(
            id="doc-contract",
            title="Sample Document",
            source_type="sermon",
            collection="contract-suite",
            authors=["Contract Tester"],
            doi=None,
            venue=None,
            year=2024,
            created_at=now,
            updated_at=now,
            provenance_score=10,
        )
        return DocumentListResponse(items=[summary], total=1, limit=limit, offset=offset)

    patcher.setattr(
        "theo.infrastructure.api.app.routes.documents.list_documents",
        _fake_list_documents,
    )

    class _StubResearchService:
        def list_notes(self, osis: str, **_kwargs) -> list[ResearchNote]:
            return [
                ResearchNote(
                    id="note-contract",
                    osis=osis,
                    body="Hope is anchored in faith.",
                    title="Hope Study",
                    stance="neutral",
                    claim_type="observation",
                    confidence=0.8,
                    tags=["hope"],
                    evidences=[],
                    created_at=now,
                    updated_at=now,
                )
            ]

    patcher.setattr(
        "theo.infrastructure.api.app.routes.research.get_research_service",
        lambda _session=None: _StubResearchService(),
    )

    class _StubRetrievalService:
        def search(self, _session, _request, *, experiments=None):
            result = HybridSearchResult(
                id="result-contract",
                document_id="doc-contract",
                text="Hope is described as an anchor.",
                raw_text=None,
                osis_ref=contract_context.osis_ref,
                start_char=None,
                end_char=None,
                page_no=None,
                t_start=None,
                t_end=None,
                score=0.95,
                meta={},
                document_title="Sample Document",
                snippet="Hope is described as an anchor.",
                rank=1,
                highlights=["Hope is described as an anchor."],
                document_score=0.95,
                document_rank=1,
                lexical_score=0.9,
                vector_score=0.9,
                osis_distance=None,
            )
            return ([result], None)

    patcher.setattr(
        "theo.infrastructure.api.app.routes.search.get_retrieval_service",
        lambda *_args, **_kwargs: _StubRetrievalService(),
    )

    def _fake_get_verse_timeline(
        session,  # noqa: ARG001
        osis: str,
        window: str,
        limit: int,
        filters,
    ) -> VerseTimelineResponse:
        bucket = VerseTimelineBucket(
            label=now.strftime("%Y-%m"),
            start=now,
            end=now,
            count=1,
            document_ids=["doc-contract"],
            sample_passage_ids=["passage-contract"],
        )
        return VerseTimelineResponse(
            osis=osis,
            window=window,
            buckets=[bucket],
            total_mentions=1,
        )

    patcher.setattr(
        "theo.infrastructure.api.app.routes.verses.get_verse_timeline",
        _fake_get_verse_timeline,
    )

    provider_store: dict[str, dict[str, object]] = {}

    def _fake_load_setting(_session, key: str, default=None):
        return provider_store.get(key, default)

    def _fake_save_setting(_session, key: str, value: dict[str, object]) -> None:
        provider_store[key] = value

    patcher.setattr(
        "theo.infrastructure.api.app.routes.ai.workflows.settings.load_setting",
        _fake_load_setting,
    )
    patcher.setattr(
        "theo.infrastructure.api.app.routes.ai.workflows.settings.save_setting",
        _fake_save_setting,
    )

    def _fake_replay_trail(self, trail, *, model_override: str | None = None):
        return TrailReplayResult(
            output={
                "trail_id": trail.id,
                "model_override": model_override,
            },
            diff={
                "changed": bool(model_override),
                "summary_changed": bool(model_override),
                "added_citations": [],
                "removed_citations": [],
            },
        )

    patcher.setattr(
        "theo.infrastructure.api.app.ai.trails.TrailService.replay_trail",
        _fake_replay_trail,
        raising=False,
    )

    try:
        yield
    finally:
        patcher.undo()


@pytest.fixture(scope="session")
def contract_client(contract_engine, contract_context) -> TestClient:  # noqa: ARG001
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
    if schemathesis_experimental is not None:
        openapi_3_1 = getattr(schemathesis_experimental, "OPEN_API_3_1", None)
        if openapi_3_1 is not None and hasattr(openapi_3_1, "enable"):
            openapi_3_1.enable()
    return schemathesis_openapi.from_asgi("/openapi.json", app)


@pytest.mark.parametrize("_suite, method, path", ENDPOINT_CASES, ids=ENDPOINT_IDS)
def test_contract_endpoints(
    _suite: str,
    method: str,
    path: str,
    openapi_schema: BaseSchema,
    contract_client: TestClient,
    contract_context: ContractTestContext,
) -> None:
    method_key = method.lower()
    operation = openapi_schema.get(path, method_key)[method_key]
    if hasattr(operation, "make_case"):
        case = operation.make_case()
    elif hasattr(operation, "Case"):
        case = operation.Case()
    else:  # pragma: no cover - compatibility fallback
        case = schemathesis.Case(operation)
    override = CASE_OVERRIDES.get((method, path))
    if override:
        if override.path_parameters:
            if case.path_parameters is None:
                case.path_parameters = {}
            case.path_parameters.update(
                _resolve_mapping(override.path_parameters, contract_context)
            )
        if override.query_parameters:
            if case.query is None:
                case.query = {}
            case.query.update(
                _resolve_mapping(override.query_parameters, contract_context)
            )
        if override.headers:
            if case.headers is None:
                case.headers = {}
            case.headers.update(
                _resolve_mapping(override.headers, contract_context)
            )
        if override.body is not None:
            case.body = _resolve_value(override.body, contract_context)
            if not getattr(case, "media_type", None):
                case.media_type = "application/json"
    response = case.call(session=contract_client)
    assert response.status_code < 500, (
        f"{method} {path} returned {response.status_code}: {response.text}"
    )
    if override and override.expected_status is not None:
        assert response.status_code == override.expected_status
    if override is None or override.validate_response:
        case.validate_response(response)
