from __future__ import annotations

import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.infrastructure.api.app.export.formatters import render_bundle  # noqa: E402
from theo.infrastructure.api.app.models.export import ExportManifest  # noqa: E402


GOLDEN_DIR = Path(__file__).with_name("golden")


@pytest.fixture()
def manifest() -> ExportManifest:
    return ExportManifest(
        export_id="export-fixture",
        schema_version="2024-07-01",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        type="search",
        filters={"query": "grace"},
        totals={"results": 1, "returned": 1},
        app_git_sha="abc1234",
        enrichment_version=2,
        cursor="passage-1",
        next_cursor=None,
        mode="results",
    )


@pytest.fixture()
def records() -> list[OrderedDict[str, object]]:
    return [
        OrderedDict(
            [
                ("kind", "result"),
                ("rank", 1),
                ("score", 0.87),
                ("document_id", "doc-1"),
                ("title", "Example Document"),
                ("snippet", "Example snippet"),
            ]
        )
    ]


@pytest.fixture()
def golden_loader() -> Path:
    if not GOLDEN_DIR.exists():
        raise AssertionError("golden directory is missing")
    return GOLDEN_DIR


def test_render_html_bundle_matches_golden(
    manifest: ExportManifest,
    records: list[OrderedDict[str, object]],
    golden_loader: Path,
) -> None:
    body, media_type = render_bundle(manifest, records, output_format="html")
    expected = (golden_loader / "export_bundle.html").read_text("utf-8")
    assert media_type == "text/html"
    assert body == expected


def test_render_obsidian_bundle_matches_golden(
    manifest: ExportManifest,
    records: list[OrderedDict[str, object]],
    golden_loader: Path,
) -> None:
    body, media_type = render_bundle(manifest, records, output_format="obsidian")
    expected = (golden_loader / "export_bundle.md").read_text("utf-8")
    assert media_type == "text/markdown"
    assert body == expected


def test_render_pdf_bundle_matches_golden(
    manifest: ExportManifest,
    records: list[OrderedDict[str, object]],
    golden_loader: Path,
) -> None:
    body, media_type = render_bundle(manifest, records, output_format="pdf")
    expected = (golden_loader / "export_bundle.pdf").read_bytes()
    assert media_type == "application/pdf"
    assert body == expected
