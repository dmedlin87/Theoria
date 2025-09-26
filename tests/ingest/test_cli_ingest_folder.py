"""Tests for the folder ingestion CLI helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.cli import ingest_folder as cli  # noqa: E402 (import after path tweak)


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("note.md", "markdown"),
        ("README.markdown", "markdown"),
        ("story.txt", "txt"),
        ("page.html", "file"),
        ("slides.htm", "file"),
        ("paper.pdf", "pdf"),
        ("captions.vtt", "transcript"),
        ("captions.json", "transcript"),
        ("thesis.docx", "docx"),
        ("archive.bin", "file"),
    ],
)
def test_detect_source_type_matches_pipeline_rules(filename: str, expected: str) -> None:
    path = Path(filename)
    assert cli._detect_source_type(path) == expected


@pytest.mark.parametrize(
    "name, is_supported",
    [
        ("document.md", True),
        ("transcript.webvtt", True),
        ("notes.txt", True),
        ("page.html", True),
        ("slides.pdf", True),
        ("metadata.json", True),
        ("draft.docx", True),
        ("binary.dat", False),
    ],
)
def test_is_supported_filters_by_extension(tmp_path: Path, name: str, is_supported: bool) -> None:
    path = tmp_path / name
    path.write_text("sample", encoding="utf-8")
    assert cli._is_supported(path) is is_supported


def test_walk_folder_discovers_supported_files(tmp_path: Path) -> None:
    supported = ["doc.md", "notes.txt", "captions.vtt"]
    unsupported = ["image.png", "archive.zip"]
    for name in supported + unsupported:
        (tmp_path / name).write_text("data", encoding="utf-8")

    discovered = list(cli._walk_folder(tmp_path))

    assert [item.path.name for item in discovered] == sorted(supported)
    assert all(item.source_type for item in discovered)


def test_parse_metadata_overrides_supports_json_values() -> None:
    overrides = cli._parse_metadata_overrides(("count=3", "enabled=true", 'tags=["a","b"]'))
    assert overrides == {"count": 3, "enabled": True, "tags": ["a", "b"]}


def test_parse_metadata_overrides_rejects_invalid_pairs() -> None:
    with pytest.raises(click.BadParameter):
        cli._parse_metadata_overrides(("missing_delimiter",))


def test_batched_groups_iterable_by_size() -> None:
    items = [cli.FolderItem(path=Path(f"file-{idx}.txt"), source_type="txt") for idx in range(5)]
    batches = list(cli._batched(items, size=2))
    assert len(batches) == 3
    assert [len(batch) for batch in batches] == [2, 2, 1]


def test_ingest_folder_dry_run_lists_batches(monkeypatch, tmp_path: Path) -> None:
    items = [
        cli.FolderItem(path=tmp_path / "first.md", source_type="markdown"),
        cli.FolderItem(path=tmp_path / "second.txt", source_type="txt"),
    ]

    monkeypatch.setattr(cli, "_walk_folder", lambda path: iter(items))
    monkeypatch.setattr(cli, "_batched", lambda iterable, size: iter([items]))

    runner = CliRunner()
    result = runner.invoke(cli.ingest_folder, [str(tmp_path), "--dry-run", "--batch-size", "1"])

    assert result.exit_code == 0
    assert "Dry-run enabled" in result.output
    assert "first.md" in result.output
    assert "second.txt" in result.output


def test_ingest_folder_uses_selected_backend(monkeypatch, tmp_path: Path) -> None:
    items = [
        cli.FolderItem(path=tmp_path / "first.md", source_type="markdown"),
        cli.FolderItem(path=tmp_path / "second.txt", source_type="txt"),
    ]

    monkeypatch.setattr(cli, "_walk_folder", lambda path: iter(items))
    monkeypatch.setattr(cli, "_batched", lambda iterable, size: iter([items]))

    ingested_batches: list[list[cli.FolderItem]] = []
    queued_batches: list[list[cli.FolderItem]] = []
    api_overrides: list[dict[str, object]] = []
    worker_overrides: list[dict[str, object]] = []

    def fake_ingest(batch, overrides, post_batch_steps=None):
        ingested_batches.append(batch)
        api_overrides.append(dict(overrides))
        assert not post_batch_steps
        return [f"doc-{idx}" for idx, _ in enumerate(batch)]

    def fake_queue(batch, overrides):
        queued_batches.append(batch)
        worker_overrides.append(dict(overrides))
        return ["queued"] * len(batch)

    monkeypatch.setattr(cli, "_ingest_batch_via_api", fake_ingest)
    monkeypatch.setattr(cli, "_queue_batch_via_worker", fake_queue)

    runner = CliRunner()
    api_result = runner.invoke(cli.ingest_folder, [str(tmp_path), "--batch-size", "2", "--meta", "flag=true"])
    worker_result = runner.invoke(cli.ingest_folder, [str(tmp_path), "--mode", "worker"])

    assert api_result.exit_code == 0
    assert worker_result.exit_code == 0
    assert len(ingested_batches) == 1
    assert len(queued_batches) == 1
    assert api_overrides == [{"flag": True}]
    assert worker_overrides == [{}]
