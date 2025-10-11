from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from theo.services.api.app.models.documents import SimpleIngestRequest
from theo.services.api.app.services.ingestion_service import IngestionService


class _StubItem:
    def __init__(self, label: str, source_type: str, remote: bool = False):
        self.label = label
        self.source_type = source_type
        self._remote = remote

    @property
    def is_remote(self) -> bool:
        return self._remote


class _StubCLI:
    def __init__(self, items: list[_StubItem]):
        self.items = items
        self.ingest_calls: list[
            tuple[list[_StubItem], dict, set | None, object | None]
        ] = []
        self.queue_calls: list[tuple[list[_StubItem], dict]] = []
        self.discovered_sources: list[str] = []

    def _discover_items(self, sources, allowlist):  # noqa: D401 - matches CLI signature
        self.discovered_sources = list(sources)
        return list(self.items)

    def _apply_default_metadata(self, metadata: dict[str, object]) -> dict[str, object]:
        enriched = dict(metadata)
        enriched.setdefault("collection", "uploads")
        return enriched

    def _parse_post_batch_steps(self, values: tuple[str, ...]) -> set[str]:
        return {value.lower() for value in values}

    def _batched(self, items, batch_size):
        for index in range(0, len(items), batch_size):
            yield items[index : index + batch_size]

    def _ingest_batch_via_api(
        self,
        batch: list[_StubItem],
        overrides: dict[str, object],
        steps: set[str] | None,
        *,
        dependencies=None,
    ) -> list[str]:
        self.ingest_calls.append((list(batch), dict(overrides), steps, dependencies))
        return [f"doc-{item.label}" for item in batch]

    def _queue_batch_via_worker(
        self, batch: list[_StubItem], overrides: dict[str, object]
    ) -> list[str]:
        self.queue_calls.append((list(batch), dict(overrides)))
        return [f"task-{index}" for index, _ in enumerate(batch, start=1)]


@pytest.fixture()
def _settings() -> SimpleNamespace:
    return SimpleNamespace(simple_ingest_allowed_roots=None)


def test_ingestion_service_ingest_file_invokes_pipeline(_settings: SimpleNamespace) -> None:
    captured: dict[str, object] = {}

    def _run_file(session, path: Path, frontmatter, *, dependencies=None):  # noqa: ANN001
        captured["session"] = session
        captured["path"] = path
        captured["frontmatter"] = frontmatter
        captured["dependencies"] = dependencies
        return SimpleNamespace(id="doc-42")

    service = IngestionService(
        settings=_settings,
        run_file_pipeline=_run_file,
        run_url_pipeline=lambda *a, **k: None,
        run_transcript_pipeline=lambda *a, **k: None,
        cli_module=_StubCLI([]),
        log_workflow=lambda *a, **k: None,
    )

    session = object()
    source_path = Path("/tmp/example.txt")
    frontmatter = {"title": "Example"}

    document = service.ingest_file(session, source_path, frontmatter)

    assert document.id == "doc-42"
    assert captured["session"] is session
    assert captured["path"] == source_path
    assert captured["frontmatter"] == frontmatter


def test_simple_ingest_api_mode_emits_expected_events(_settings: SimpleNamespace) -> None:
    items = [
        _StubItem("a", "markdown"),
        _StubItem("b", "pdf"),
        _StubItem("c", "markdown"),
    ]
    cli = _StubCLI(items)
    workflow_events: list[tuple[str, dict]] = []

    def _log(event: str, **payload):
        workflow_events.append((event, payload))

    service = IngestionService(
        settings=_settings,
        run_file_pipeline=lambda *a, **k: SimpleNamespace(id="doc"),
        run_url_pipeline=lambda *a, **k: SimpleNamespace(id="doc"),
        run_transcript_pipeline=lambda *a, **k: SimpleNamespace(id="doc"),
        cli_module=cli,
        log_workflow=_log,
    )

    payload = SimpleIngestRequest(
        sources=["/data"],
        mode="api",
        batch_size=2,
        metadata={"collection": "custom"},
    )

    events = list(service.stream_simple_ingest(payload))

    assert events[:1] == [
        {
            "event": "start",
            "total": 3,
            "mode": "api",
            "dry_run": False,
            "batch_size": 2,
        }
    ]
    assert [event for event in events if event["event"] == "discovered"] == [
        {"event": "discovered", "target": item.label, "source_type": item.source_type, "remote": False}
        for item in items
    ]
    processed = [event for event in events if event["event"] == "processed"]
    assert [entry["document_id"] for entry in processed] == ["doc-a", "doc-b", "doc-c"]
    assert events[-1] == {
        "event": "complete",
        "processed": 3,
        "queued": 0,
        "total": 3,
        "mode": "api",
    }

    assert cli.ingest_calls[0][1]["collection"] == "custom"
    assert cli.ingest_calls[0][2] == set()
    assert workflow_events[0][0] == "api.simple_ingest.started"
    assert workflow_events[-1][0] == "api.simple_ingest.completed"


def test_simple_ingest_worker_mode_warns_on_post_batch(_settings: SimpleNamespace) -> None:
    item = _StubItem("remote", "web", remote=True)
    cli = _StubCLI([item])
    workflow_events: list[tuple[str, dict]] = []

    def _log(event: str, **payload):
        workflow_events.append((event, payload))

    service = IngestionService(
        settings=_settings,
        run_file_pipeline=lambda *a, **k: SimpleNamespace(id="doc"),
        run_url_pipeline=lambda *a, **k: SimpleNamespace(id="doc"),
        run_transcript_pipeline=lambda *a, **k: SimpleNamespace(id="doc"),
        cli_module=cli,
        log_workflow=_log,
    )

    payload = SimpleIngestRequest(
        sources=["https://example.com"],
        mode="worker",
        post_batch=["tags"],
        batch_size=1,
    )

    events = list(service.stream_simple_ingest(payload))

    warning = next(event for event in events if event["event"] == "warning")
    assert "Post-batch steps require API mode" in warning["message"]

    queued = next(event for event in events if event["event"] == "queued")
    assert queued["target"] == "remote"
    assert queued["task_id"].startswith("task-")

    assert workflow_events[-1][1]["queued"] == 1
    assert cli.queue_calls
