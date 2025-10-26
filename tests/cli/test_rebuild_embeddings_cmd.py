from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from theo.application.embeddings import (
    EmbeddingRebuildError,
    EmbeddingRebuildOptions,
    EmbeddingRebuildProgress,
    EmbeddingRebuildResult,
    EmbeddingRebuildService,
    EmbeddingRebuildStart,
    EmbeddingRebuildState,
)
from theo.cli import cli, rebuild_embeddings_cmd


class StubEmbeddingRebuildService(EmbeddingRebuildService):
    def __init__(self) -> None:
        self.calls: list[EmbeddingRebuildOptions] = []
        self.progress_events: list[EmbeddingRebuildProgress] = []
        self.start_events: list[EmbeddingRebuildStart] = []
        self.result = EmbeddingRebuildResult(
            processed=1,
            total=1,
            duration=0.5,
            missing_ids=[],
            metadata={},
        )

    # type: ignore[override]
    def rebuild_embeddings(
        self,
        options: EmbeddingRebuildOptions,
        *,
        on_start=None,
        on_progress=None,
    ) -> EmbeddingRebuildResult:
        self.calls.append(options)
        if on_start is not None:
            start = EmbeddingRebuildStart(total=1, missing_ids=[], skip_count=0)
            self.start_events.append(start)
            on_start(start)
        if on_progress is not None:
            state = EmbeddingRebuildState(
                processed=1,
                total=1,
                last_id="p1",
                metadata=options.metadata,
            )
            progress = EmbeddingRebuildProgress(
                batch_index=1,
                batch_size=1,
                batch_duration=0.1,
                rate_per_passage=0.1,
                state=state,
            )
            self.progress_events.append(progress)
            on_progress(progress)
        return self.result


class FailingEmbeddingRebuildService(StubEmbeddingRebuildService):
    def rebuild_embeddings(self, *args: Any, **kwargs: Any) -> EmbeddingRebuildResult:
        raise EmbeddingRebuildError("boom")


class FakeRegistry:
    def __init__(self, service: EmbeddingRebuildService) -> None:
        self.service = service

    def resolve(self, name: str) -> EmbeddingRebuildService:
        if name != "embedding_rebuild_service":  # pragma: no cover - defensive
            raise LookupError(name)
        return self.service


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def _patch_registry(monkeypatch: pytest.MonkeyPatch, service: EmbeddingRebuildService) -> None:
    def _resolve_application() -> tuple[object, FakeRegistry]:
        return object(), FakeRegistry(service)

    monkeypatch.setattr("theo.cli.resolve_application", _resolve_application)


def test_cli_rebuild_embeddings_invokes_service(monkeypatch: pytest.MonkeyPatch, runner: CliRunner) -> None:
    service = StubEmbeddingRebuildService()
    _patch_registry(monkeypatch, service)

    result = runner.invoke(rebuild_embeddings_cmd, ["--fast"])

    assert result.exit_code == 0, result.output
    assert "Rebuilding embeddings for 1 passage(s)" in result.output
    assert "Batch 1: updated 1/1 passages" in result.output
    assert "Completed embedding rebuild for 1 passage(s)" in result.output
    assert service.calls


def test_cli_handles_checkpoint_resume(monkeypatch: pytest.MonkeyPatch, runner: CliRunner, tmp_path: Path) -> None:
    service = StubEmbeddingRebuildService()
    _patch_registry(monkeypatch, service)

    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(json.dumps({"processed": 2}), encoding="utf-8")

    result = runner.invoke(
        rebuild_embeddings_cmd,
        ["--checkpoint-file", str(checkpoint), "--resume"],
    )

    assert result.exit_code == 0, result.output
    assert "Resuming from checkpoint" in result.output
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert payload["processed"] == 1
    assert payload["total"] == 1
    assert payload["last_id"] == "p1"
    assert "Checkpoint written" in result.output


def test_cli_handles_empty_ids_file(monkeypatch: pytest.MonkeyPatch, runner: CliRunner, tmp_path: Path) -> None:
    service = StubEmbeddingRebuildService()
    _patch_registry(monkeypatch, service)

    ids_file = tmp_path / "ids.txt"
    ids_file.write_text("\n\n", encoding="utf-8")

    result = runner.invoke(
        rebuild_embeddings_cmd,
        ["--ids-file", str(ids_file)],
    )

    assert result.exit_code == 0, result.output
    assert "No passage IDs were found" in result.output


def test_cli_handles_service_error(monkeypatch: pytest.MonkeyPatch, runner: CliRunner) -> None:
    service = FailingEmbeddingRebuildService()
    _patch_registry(monkeypatch, service)

    result = runner.invoke(rebuild_embeddings_cmd, ["--fast"])

    assert result.exit_code == 1
    assert "boom" in result.output


def test_cli_help_lists_rebuild_command(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "rebuild_embeddings" in result.output


def test_cli_handles_application_resolution_failure(monkeypatch: pytest.MonkeyPatch, runner: CliRunner) -> None:
    def _fail() -> tuple[object, object]:
        raise RuntimeError("boom")

    monkeypatch.setattr("theo.cli.resolve_application", _fail)

    result = runner.invoke(rebuild_embeddings_cmd, ["--fast"])

    assert result.exit_code == 1
    assert "Failed to resolve application" in result.output
