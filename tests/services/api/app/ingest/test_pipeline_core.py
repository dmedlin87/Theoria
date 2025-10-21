from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

from theo.services.api.app.ingest.exceptions import UnsupportedSourceError
from theo.services.api.app.ingest.orchestrator import OrchestratorResult, StageExecution
from theo.services.api.app.ingest.pipeline import (
    PipelineDependencies,
    _ensure_success,
    _file_title_default,
    _transcript_title_default,
    run_pipeline_for_url,
)


class _SentinelSettings:
    ingest_url_allowed_hosts: list[str] = []
    ingest_url_blocked_hosts: list[str] = []
    ingest_url_blocked_ip_networks: list[str] = []
    ingest_url_allowed_schemes: list[str] = ["http", "https"]
    ingest_url_blocked_schemes: list[str] = []
    ingest_url_block_private_networks: bool = True


class _SentinelEmbedding:
    def embed(self, texts):  # pragma: no cover - behaviour unused in tests
        return texts


class _SentinelErrorPolicy:
    def decide(self, **_):  # pragma: no cover - behaviour unused in tests
        raise AssertionError("Error policy should not be consulted")


def _fake_setter(span, key, value):
    span.setdefault("attributes", []).append((key, value))


def test_pipeline_dependencies_prefers_explicit_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    from theo.services.api.app.ingest import pipeline

    monkeypatch.setattr(pipeline, "get_settings", lambda: (_ for _ in ()).throw(AssertionError))
    monkeypatch.setattr(
        pipeline,
        "get_embedding_service",
        lambda: (_ for _ in ()).throw(AssertionError),
    )
    span = {"attributes": []}
    monkeypatch.setattr(pipeline, "set_span_attribute", _fake_setter)

    dependencies = PipelineDependencies(
        settings=_SentinelSettings(),
        embedding_service=_SentinelEmbedding(),
        error_policy=_SentinelErrorPolicy(),
        graph_projector=object(),
    )

    context = dependencies.build_context(span=span)

    assert context.settings is dependencies.settings
    assert context.embedding_service is dependencies.embedding_service
    assert context.error_policy is dependencies.error_policy
    assert context.graph_projector is dependencies.graph_projector

    context.instrumentation.set("foo", "bar")
    assert span["attributes"] == [("foo", "bar")]


def test_pipeline_dependencies_falls_back_to_null_graph_projector(monkeypatch: pytest.MonkeyPatch) -> None:
    from theo.services.api.app.ingest import pipeline

    sentinel_settings = _SentinelSettings()
    sentinel_embedding = _SentinelEmbedding()

    monkeypatch.setattr(pipeline, "get_settings", lambda: sentinel_settings)
    monkeypatch.setattr(pipeline, "get_embedding_service", lambda: sentinel_embedding)

    def failing_graph_projector():
        raise RuntimeError("boom")

    monkeypatch.setattr(pipeline, "get_graph_projector", failing_graph_projector)

    dependencies = PipelineDependencies()
    context = dependencies.build_context(span=None)

    assert context.settings is sentinel_settings
    assert context.embedding_service is sentinel_embedding
    assert isinstance(context.graph_projector, pipeline.NullGraphProjector)


def test_ensure_success_returns_document_on_success() -> None:
    document = object()
    result = OrchestratorResult(
        status="success",
        state={"document": document},
        stages=[],
        failures=[],
    )

    assert _ensure_success(result) is document


def test_ensure_success_raises_original_error() -> None:
    error = RuntimeError("failure")
    failure = StageExecution(
        name="stage",
        status="failed",
        attempts=1,
        data=None,
        error=error,
    )
    result = OrchestratorResult(status="failed", state={}, stages=[], failures=[failure])

    with pytest.raises(RuntimeError) as excinfo:
        _ensure_success(result)

    assert excinfo.value is error


def test_ensure_success_raises_when_missing_error_metadata() -> None:
    failure = StageExecution(
        name="stage",
        status="failed",
        attempts=1,
        data=None,
        error=None,
    )
    result = OrchestratorResult(status="failed", state={}, stages=[], failures=[failure])

    with pytest.raises(UnsupportedSourceError) as excinfo:
        _ensure_success(result)

    assert "error metadata" in str(excinfo.value)


def test_ensure_success_raises_from_last_stage_when_failures_missing_error() -> None:
    stage = StageExecution(
        name="stage",
        status="failed",
        attempts=1,
        data=None,
        error=ValueError("stage failed"),
    )
    result = OrchestratorResult(status="failed", state={}, stages=[stage], failures=[])

    with pytest.raises(ValueError):
        _ensure_success(result)


def test_file_title_default_prefers_path_objects() -> None:
    assert _file_title_default({"path": Path("/tmp/example.md")}) == "example"
    assert _file_title_default({"path": "/tmp/report.txt"}) == "report"
    assert _file_title_default({}) == "Document"


def test_transcript_title_default_prefers_path_objects() -> None:
    assert _transcript_title_default({"transcript_path": Path("/tmp/video.vtt")}) == "video"
    assert _transcript_title_default({"transcript_path": "video.vtt"}) == "Transcript"
    assert _transcript_title_default({}) == "Transcript"


class _FakeTextDocumentPersister:
    name = "text"

    def __init__(self, *, session) -> None:
        self.session = session
        self.calls: list[dict[str, object]] = []

    def persist(self, *, context, state):
        self.calls.append({"context": context, "state": dict(state)})
        return {"document": "text"}


class _FakeTranscriptDocumentPersister:
    name = "transcript"

    def __init__(self, *, session) -> None:
        self.session = session
        self.calls: list[dict[str, object]] = []

    def persist(self, *, context, state):
        self.calls.append({"context": context, "state": dict(state)})
        return {"document": "transcript"}


class _FakeSpan:
    def __init__(self) -> None:
        self.attributes: list[tuple[str, object]] = []

    def set_attribute(self, key, value) -> None:
        self.attributes.append((key, value))


@contextmanager
def _fake_instrument_workflow(*_, **__):
    yield _FakeSpan()


def test_url_document_persister_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    from theo.services.api.app.ingest import pipeline

    text_instances: list[_FakeTextDocumentPersister] = []
    transcript_instances: list[_FakeTranscriptDocumentPersister] = []

    monkeypatch.setattr(pipeline, "TextDocumentPersister", lambda *, session: _track_instance(_FakeTextDocumentPersister, text_instances, session=session))
    monkeypatch.setattr(pipeline, "TranscriptDocumentPersister", lambda *, session: _track_instance(_FakeTranscriptDocumentPersister, transcript_instances, session=session))
    monkeypatch.setattr(pipeline, "instrument_workflow", _fake_instrument_workflow)

    captured: dict[str, list[object]] = {}

    def fake_orchestrator(stages):
        captured["stages"] = list(stages)

        class _Runner:
            def run(self, *, context):
                return OrchestratorResult(
                    status="success",
                    state={"document": "result"},
                    stages=[],
                    failures=[],
                )

        return _Runner()

    monkeypatch.setattr(pipeline, "_default_orchestrator", fake_orchestrator)

    dependencies = PipelineDependencies(
        settings=_SentinelSettings(),
        embedding_service=_SentinelEmbedding(),
        error_policy=_SentinelErrorPolicy(),
        graph_projector=object(),
    )

    result = run_pipeline_for_url(
        session=object(),
        url="https://example.com/article",
        source_type=None,
        dependencies=dependencies,
    )

    assert result == "result"
    persister = captured["stages"][-1]
    assert hasattr(persister, "persist")
    assert hasattr(persister, "_text_persister")

    context = object()
    youtube_state = {"source_type": "youtube", "document": object()}
    text_state = {"source_type": "web_page", "document": object()}

    youtube_result = persister.persist(context=context, state=youtube_state)
    text_result = persister.persist(context=context, state=text_state)

    assert youtube_result == {"document": "transcript"}
    assert text_result == {"document": "text"}

    assert text_instances and transcript_instances
    assert transcript_instances[0].calls[-1]["state"]["source_type"] == "youtube"
    assert text_instances[0].calls[-1]["state"]["source_type"] == "web_page"


def _track_instance(cls, storage, *, session):
    instance = cls(session=session)
    storage.append(instance)
    return instance

