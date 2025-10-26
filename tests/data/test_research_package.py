"""Integration tests for theo.data.research resource helpers."""
from __future__ import annotations

import json
from importlib import resources

import pytest

research = pytest.importorskip(
    "theo.data.research", reason="theo.data.research package is not available"
)

RESOURCE_ROOT = research.files()
SAMPLE_FILENAME = "scripture.json"
EXPECTED_FILENAMES = {
    "crossrefs.json",
    "dss_links.json",
    "historicity.json",
    "morphology.json",
    "report_templates.json",
    "scripture.json",
    "variants.json",
}

if not RESOURCE_ROOT.joinpath(SAMPLE_FILENAME).is_file():
    pytest.skip(
        f"Research dataset '{SAMPLE_FILENAME}' not packaged", allow_module_level=True
    )


def _require_resource(name: str) -> resources.abc.Traversable:
    resource = RESOURCE_ROOT.joinpath(name)
    if not resource.is_file():
        pytest.skip(f"Research dataset '{name}' not packaged")
    return resource


def test_files_returns_expected_traversable() -> None:
    """files() should expose the same traversable as importlib.resources.files."""

    package_files = research.files()
    canonical_files = resources.files(research.__name__)
    assert package_files == canonical_files

    available = {entry.name for entry in package_files.iterdir() if entry.is_file()}
    missing = EXPECTED_FILENAMES - available
    if missing:
        pytest.skip(f"Bundled research assets missing: {sorted(missing)}")

    assert EXPECTED_FILENAMES <= available


def test_open_text_respects_encoding() -> None:
    resource = _require_resource(SAMPLE_FILENAME)

    with research.open_text(resource.name, encoding="utf-8") as handle:
        payload = json.load(handle)

    verse = payload["SBLGNT"]["John.1.1"]["text"]
    assert verse.startswith("Ἐν ἀρχῆ ἦν ὁ Λόγος")


def test_read_text_matches_open_text() -> None:
    resource = _require_resource(SAMPLE_FILENAME)

    text_data = research.read_text(resource.name, encoding="utf-8")
    with research.open_text(resource.name, encoding="utf-8") as handle:
        assert handle.read() == text_data


def test_open_binary_reads_bytes() -> None:
    resource = _require_resource(SAMPLE_FILENAME)

    with research.open_binary(resource.name) as handle:
        binary_prefix = handle.read(8)

    assert isinstance(binary_prefix, bytes)
    assert binary_prefix.startswith(b"{")


def test_read_binary_matches_open_binary() -> None:
    resource = _require_resource(SAMPLE_FILENAME)

    open_bytes: bytes
    with research.open_binary(resource.name) as handle:
        open_bytes = handle.read()

    direct_bytes = research.read_binary(resource.name)
    assert direct_bytes == open_bytes

