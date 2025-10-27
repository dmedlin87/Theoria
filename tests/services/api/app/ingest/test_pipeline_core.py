from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

from theo.infrastructure.api.app.ingest.exceptions import UnsupportedSourceError
from theo.infrastructure.api.app.ingest.orchestrator import OrchestratorResult, StageExecution
from theo.infrastructure.api.app.ingest.pipeline import (
    PipelineDependencies,
    _ensure_success,
    _file_title_default,
    _transcript_title_default,
    _url_title_default,
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


class _RecordingDependencies:
    def __init__(self, context: object) -> None:
        self._context = context
        self.calls: int = 0
        self.captured_span: object | None = None

    def build_context(self, *, span):
        self.calls += 1
        self.captured_span = span
        return self._context


def test_pipeline_dependencies_prefers_explicit_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    from theo.infrastructure.api.app.ingest import pipeline

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
    from theo.infrastructure.api.app.ingest import pipeline

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


def test_url_title_default_prefers_youtube_video_id() -> None:
    state = {"source_type": "youtube", "video_id": "abc123"}
    assert _url_title_default(state) == "YouTube Video abc123"


def test_url_title_default_falls_back_to_source_url() -> None:
    assert _url_title_default({"url": "https://example.com"}) == "https://example.com"
    assert _url_title_default({}) == "Document"


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
    from theo.infrastructure.api.app.ingest import pipeline

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


def test_orchestrate_uses_dependencies_and_records_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    from theo.infrastructure.api.app.ingest import pipeline

    captured: dict[str, object] = {}

    @contextmanager
    def fake_instrument_workflow(workflow: str, **attrs):
        captured["workflow"] = workflow
        captured["attrs"] = attrs
        span = _FakeSpan()
        captured["span"] = span
        yield span

    monkeypatch.setattr(pipeline, "instrument_workflow", fake_instrument_workflow)

    fake_dependencies = _RecordingDependencies(context=object())
    monkeypatch.setattr(pipeline, "_default_orchestrator", lambda stages: _RunnerSuccess(stages, captured))

    document = pipeline._orchestrate(
        session=object(),
        dependencies=fake_dependencies,
        stages=["stage"],
        workflow="ingest.custom",
        workflow_kwargs={"source": "test"},
    )

    assert document == "document"
    assert captured["workflow"] == "ingest.custom"
    assert captured["attrs"] == {"source": "test"}
    assert fake_dependencies.calls == 1
    assert fake_dependencies.captured_span is captured["span"]
    assert captured["context"] is fake_dependencies._context
    assert captured["stages"] == ["stage"]


def test_orchestrate_instantiates_dependencies_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from theo.infrastructure.api.app.ingest import pipeline

    created: list[_RecordingDependencies] = []

    class _Factory(_RecordingDependencies):
        def __init__(self):
            super().__init__(context=object())
            created.append(self)

    monkeypatch.setattr(pipeline, "PipelineDependencies", _Factory)

    captured: dict[str, object] = {}

    @contextmanager
    def fake_instrument_workflow(*_, **__):
        span = _FakeSpan()
        captured["span"] = span
        yield span

    monkeypatch.setattr(pipeline, "instrument_workflow", fake_instrument_workflow)
    monkeypatch.setattr(pipeline, "_default_orchestrator", lambda stages: _RunnerSuccess(stages, captured))

    result = pipeline._orchestrate(
        session=object(),
        dependencies=None,
        stages=["fetch", "parse"],
        workflow="ingest.auto",
        workflow_kwargs={},
    )

    assert result == "document"
    assert created, "PipelineDependencies should be instantiated when missing"
    dependency = created[0]
    assert dependency.captured_span is captured["span"]
    assert captured["stages"] == ["fetch", "parse"]


def test_run_pipeline_for_file_wires_expected_stages(monkeypatch: pytest.MonkeyPatch) -> None:
    from theo.infrastructure.api.app.ingest import pipeline

    session = object()
    path = Path("/tmp/source.md")
    fake_dependencies = _RecordingDependencies(context=object())

    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        pipeline,
        "load_frontmatter",
        lambda payload: calls.append(("load_frontmatter", payload)) or {"title": "Doc"},
    )
    monkeypatch.setattr(
        pipeline,
        "merge_metadata",
        lambda base, loaded: calls.append(("merge_metadata", (base, loaded))) or {"merged": True},
    )

    captured: dict[str, object] = {}

    @contextmanager
    def fake_instrument_workflow(workflow: str, **attrs):
        captured["workflow"] = workflow
        captured["attrs"] = attrs
        span = _FakeSpan()
        captured["span"] = span
        yield span

    monkeypatch.setattr(pipeline, "instrument_workflow", fake_instrument_workflow)
    monkeypatch.setattr(pipeline, "_default_orchestrator", lambda stages: _RunnerSuccess(stages, captured))

    result = pipeline.run_pipeline_for_file(
        session=session,
        path=path,
        frontmatter={"title": "Example"},
        dependencies=fake_dependencies,
    )

    assert result == "document"
    assert calls[0] == ("load_frontmatter", {"title": "Example"})
    assert calls[1][0] == "merge_metadata"
    stages = captured["stages"]
    assert isinstance(stages[0], pipeline.FileSourceFetcher)
    assert stages[0].frontmatter == {"merged": True}
    assert isinstance(stages[1], pipeline.FileParser)
    assert isinstance(stages[2], pipeline.DocumentEnricher)
    assert isinstance(stages[3], pipeline.TextDocumentPersister)
    assert stages[3].session is session
    assert fake_dependencies.captured_span is captured["span"]
    assert captured["workflow"] == "ingest.file"
    assert captured["attrs"] == {"source_path": str(path), "source_name": path.name}


def test_run_pipeline_for_transcript_wires_expected_stages(monkeypatch: pytest.MonkeyPatch) -> None:
    from theo.infrastructure.api.app.ingest import pipeline

    session = object()
    transcript_path = Path("/tmp/audio.vtt")
    fake_dependencies = _RecordingDependencies(context=object())

    monkeypatch.setattr(pipeline, "load_frontmatter", lambda payload: {"channel": "Main"})
    monkeypatch.setattr(pipeline, "merge_metadata", lambda base, loaded: loaded)

    captured: dict[str, object] = {}

    @contextmanager
    def fake_instrument_workflow(workflow: str, **attrs):
        captured["workflow"] = workflow
        captured["attrs"] = attrs
        span = _FakeSpan()
        captured["span"] = span
        yield span

    monkeypatch.setattr(pipeline, "instrument_workflow", fake_instrument_workflow)
    monkeypatch.setattr(pipeline, "_default_orchestrator", lambda stages: _RunnerSuccess(stages, captured))

    result = pipeline.run_pipeline_for_transcript(
        session=session,
        transcript_path=transcript_path,
        dependencies=fake_dependencies,
        audio_path=Path("/tmp/audio.mp3"),
        transcript_filename="audio.vtt",
        audio_filename="audio.mp3",
    )

    assert result == "document"
    stages = captured["stages"]
    assert isinstance(stages[0], pipeline.TranscriptSourceFetcher)
    assert stages[0].transcript_path == transcript_path
    assert stages[0].audio_path == Path("/tmp/audio.mp3")
    assert stages[0].transcript_filename == "audio.vtt"
    assert stages[0].audio_filename == "audio.mp3"
    assert isinstance(stages[1], pipeline.TranscriptParser)
    assert isinstance(stages[2], pipeline.DocumentEnricher)
    assert isinstance(stages[3], pipeline.TranscriptDocumentPersister)
    assert stages[3].session is session
    assert fake_dependencies.captured_span is captured["span"]
    assert captured["workflow"] == "ingest.transcript"
    assert captured["attrs"] == {
        "transcript_path": str(transcript_path),
        "audio_path": str(Path("/tmp/audio.mp3")),
    }


def test_import_osis_commentary_returns_result(monkeypatch: pytest.MonkeyPatch) -> None:
    from theo.infrastructure.api.app.ingest import pipeline

    session = object()
    path = Path("/tmp/commentary.xml")
    fake_dependencies = _RecordingDependencies(context=object())

    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        pipeline,
        "load_frontmatter",
        lambda payload: calls.append(("load_frontmatter", payload)) or {"title": "OSIS"},
    )
    monkeypatch.setattr(
        pipeline,
        "merge_metadata",
        lambda base, loaded: calls.append(("merge_metadata", (base, loaded))) or {"merged": True},
    )

    captured: dict[str, object] = {}

    @contextmanager
    def fake_instrument_workflow(workflow: str, **attrs):
        captured["workflow"] = workflow
        captured["attrs"] = attrs
        span = _FakeSpan()
        captured["span"] = span
        yield span

    monkeypatch.setattr(pipeline, "instrument_workflow", fake_instrument_workflow)
    monkeypatch.setattr(
        pipeline,
        "_default_orchestrator",
        lambda stages: _RunnerSuccess(stages, captured, state_key="commentary_result"),
    )

    result = pipeline.import_osis_commentary(
        session=session,
        path=path,
        dependencies=fake_dependencies,
    )

    assert result == "document"
    assert calls[0] == ("load_frontmatter", None)
    stages = captured["stages"]
    assert isinstance(stages[0], pipeline.OsisSourceFetcher)
    assert stages[0].path == path
    assert stages[0].frontmatter == {"merged": True}
    assert isinstance(stages[1], pipeline.OsisCommentaryParser)
    assert isinstance(stages[2], pipeline.CommentarySeedPersister)
    assert stages[2].session is session
    assert fake_dependencies.captured_span is captured["span"]
    assert captured["workflow"] == "ingest.osis"
    assert captured["attrs"] == {
        "source_path": str(path),
        "source_name": path.name,
    }


def test_import_osis_commentary_raises_when_missing_result(monkeypatch: pytest.MonkeyPatch) -> None:
    from theo.infrastructure.api.app.ingest import pipeline

    @contextmanager
    def fake_instrument_workflow(*_, **__):
        yield _FakeSpan()

    monkeypatch.setattr(pipeline, "instrument_workflow", fake_instrument_workflow)
    monkeypatch.setattr(
        pipeline,
        "_default_orchestrator",
        lambda stages: _RunnerWithResult(
            OrchestratorResult(status="success", state={}, stages=[], failures=[])
        ),
    )

    with pytest.raises(UnsupportedSourceError):
        pipeline.import_osis_commentary(
            session=object(),
            path=Path("/tmp/commentary.xml"),
        )


def test_import_osis_commentary_reraises_failure_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from theo.infrastructure.api.app.ingest import pipeline

    error = RuntimeError("boom")
    failure = StageExecution(
        name="persist",
        status="failed",
        attempts=1,
        data=None,
        error=error,
    )

    @contextmanager
    def fake_instrument_workflow(*_, **__):
        yield _FakeSpan()

    monkeypatch.setattr(pipeline, "instrument_workflow", fake_instrument_workflow)
    monkeypatch.setattr(
        pipeline,
        "_default_orchestrator",
        lambda stages: _RunnerWithResult(
            OrchestratorResult(status="failed", state={}, stages=[], failures=[failure])
        ),
    )

    with pytest.raises(RuntimeError) as excinfo:
        pipeline.import_osis_commentary(
            session=object(),
            path=Path("/tmp/commentary.xml"),
        )

    assert excinfo.value is error


class _RunnerSuccess:
    def __init__(self, stages, captured: dict[str, object], *, state_key: str = "document") -> None:
        captured["stages"] = list(stages)
        self._captured = captured
        self._state_key = state_key

    def run(self, *, context, **_):
        self._captured["context"] = context
        return OrchestratorResult(
            status="success",
            state={self._state_key: "document"},
            stages=[],
            failures=[],
        )


class _RunnerWithResult:
    def __init__(self, result: OrchestratorResult) -> None:
        self._result = result

    def run(self, *, context=None, **_):
        return self._result

