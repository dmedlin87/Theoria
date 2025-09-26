"""Tests for the bulk ingestion CLI."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.core import settings as settings_module
from theo.services.api.app.core.database import Base, configure_engine
from theo.services.api.app.db.models import Document
from theo.services.cli.ingest_folder import ingest_folder


@pytest.fixture(autouse=True)
def configure_cli_environment(tmp_path):
    db_path = tmp_path / "cli.db"
    storage_root = tmp_path / "storage"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"  # ensure isolation
    os.environ["STORAGE_ROOT"] = str(storage_root)
    os.environ["FIXTURES_ROOT"] = str(tmp_path)

    settings_module.get_settings.cache_clear()
    settings = settings_module.get_settings()
    engine = configure_engine(settings.database_url)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    yield

    settings_module.get_settings.cache_clear()
    shutil.rmtree(storage_root, ignore_errors=True)
    if db_path.exists():
        db_path.unlink()


def test_dry_run_lists_supported_files(tmp_path, monkeypatch):
    (tmp_path / "nested").mkdir()
    supported_md = tmp_path / "nested" / "teaching.md"
    supported_md.write_text("---\ntitle: Example\n---\nBody")
    supported_pdf = tmp_path / "notes.pdf"
    supported_pdf.write_bytes(b"%PDF-1.4")
    ignored = tmp_path / "image.png"
    ignored.write_bytes(b"not-a-real-image")

    calls: list = []

    def _fail_if_called(*args, **kwargs):  # pragma: no cover - safety
        calls.append((args, kwargs))
        raise AssertionError("run_pipeline_for_file should not be invoked during dry-run")

    monkeypatch.setattr("theo.services.cli.ingest_folder.run_pipeline_for_file", _fail_if_called)

    runner = CliRunner()
    result = runner.invoke(
        ingest_folder,
        [
            str(tmp_path),
            "--dry-run",
            "--batch-size",
            "2",
            "--meta",
            "collection=sermons",
        ],
    )

    assert result.exit_code == 0
    assert "Discovered 2 supported file(s)" in result.output
    assert "teaching.md" in result.output
    assert "notes.pdf" in result.output
    assert "Dry-run enabled" in result.output
    assert not calls
    assert "image.png" not in result.output


def test_api_mode_processes_batches_with_overrides(tmp_path, monkeypatch):
    first = tmp_path / "study.md"
    first.write_text("Content")
    second = tmp_path / "transcript.vtt"
    second.write_text("WEBVTT\n\n00:00.000 --> 00:05.000\nHello")

    ingested: list[tuple[str, dict[str, object]]] = []

    def _fake_run_pipeline(session, path, frontmatter):
        ingested.append((str(path), dict(frontmatter)))
        return SimpleNamespace(id=f"doc-{len(ingested)}", source_type="markdown", title=path.stem)

    monkeypatch.setattr("theo.services.cli.ingest_folder.run_pipeline_for_file", _fake_run_pipeline)

    runner = CliRunner()
    result = runner.invoke(
        ingest_folder,
        [
            str(tmp_path),
            "--batch-size",
            "1",
            "--meta",
            'collection="sermons"',
            "--meta",
            'authors=["John"]',
        ],
    )

    assert result.exit_code == 0
    assert len(ingested) == 2
    assert ingested[0][1]["collection"] == "sermons"
    assert ingested[0][1]["authors"] == ["John"]
    assert "Processed" in result.output


def test_worker_mode_enqueues_tasks(tmp_path, monkeypatch):
    audio = tmp_path / "lecture.json"
    audio.write_text("{}")

    queued: list[tuple[str, str, dict[str, object]]] = []

    class _FakeAsyncResult:
        def __init__(self, task_id: str) -> None:
            self.id = task_id

    class _FakeProcessFile:
        def delay(self, doc_id: str, path: str, frontmatter: dict[str, object]):
            queued.append((doc_id, path, dict(frontmatter)))
            return _FakeAsyncResult(f"task-{len(queued)}")

    monkeypatch.setattr(
        "theo.services.cli.ingest_folder.worker_tasks.process_file",
        _FakeProcessFile(),
    )
    def _unexpected(*args, **kwargs):
        raise AssertionError("Should not call API mode")

    monkeypatch.setattr("theo.services.cli.ingest_folder.run_pipeline_for_file", _unexpected)

    runner = CliRunner()
    result = runner.invoke(
        ingest_folder,
        [
            str(tmp_path / "lecture.json"),
            "--mode",
            "worker",
            "--meta",
            "collection=bulk",
        ],
    )

    assert result.exit_code == 0
    assert len(queued) == 1
    doc_id, path, frontmatter = queued[0]
    assert path.endswith("lecture.json")
    assert frontmatter["collection"] == "bulk"
    assert "Queued" in result.output


def test_post_batch_tags_runs_enricher(tmp_path, monkeypatch):
    doc_path = tmp_path / "note.md"
    doc_path.write_text("---\ntitle: Example\n---\nBody")

    calls: list[str] = []

    class _FakeEnricher:
        def __init__(self) -> None:
            pass

        def enrich_document(self, session, document):
            calls.append(document.id)
            return True

    def _fake_run_pipeline(session, path, frontmatter):
        document = Document(
            id=f"doc-{path.stem}",
            title=frontmatter.get("title") if frontmatter else None,
            source_type="markdown",
        )
        session.add(document)
        session.flush()
        return document

    monkeypatch.setattr(
        "theo.services.cli.ingest_folder.MetadataEnricher",
        _FakeEnricher,
    )
    monkeypatch.setattr(
        "theo.services.cli.ingest_folder.run_pipeline_for_file",
        _fake_run_pipeline,
    )

    runner = CliRunner()
    result = runner.invoke(
        ingest_folder,
        [str(doc_path), "--batch-size", "1", "--post-batch", "tags"],
    )

    assert result.exit_code == 0
    assert calls, "Expected metadata enrichment to run"
    assert "[post-batch:tags] enriched" in result.output


def test_post_batch_skipped_for_worker_mode(tmp_path, monkeypatch):
    source = tmp_path / "lecture.json"
    source.write_text("{}")

    class _FakeAsyncResult:
        def __init__(self, task_id: str) -> None:
            self.id = task_id

    class _FakeProcessFile:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def delay(self, doc_id: str, path: str, frontmatter: dict[str, object]):
            self.calls.append((doc_id, path))
            return _FakeAsyncResult(f"task-{len(self.calls)}")

    fake_worker = _FakeProcessFile()
    monkeypatch.setattr(
        "theo.services.cli.ingest_folder.worker_tasks.process_file",
        fake_worker,
    )
    monkeypatch.setattr(
        "theo.services.cli.ingest_folder.run_pipeline_for_file",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("API mode should not run")),
    )
    monkeypatch.setattr(
        "theo.services.cli.ingest_folder.MetadataEnricher",
        lambda: (_ for _ in ()).throw(AssertionError("Post-batch should be skipped")),
    )

    runner = CliRunner()
    result = runner.invoke(
        ingest_folder,
        [str(source), "--mode", "worker", "--post-batch", "tags"],
    )

    assert result.exit_code == 0
    assert "Post-batch steps require API mode" in result.output
    assert fake_worker.calls
