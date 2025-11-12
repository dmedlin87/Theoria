from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

geo = importlib.import_module("theo.infrastructure.geo.seed_openbible_geo")


def test_normalize_osis_returns_canonical_references() -> None:
    references = geo._normalize_osis("John.3.16")
    assert references == ["John.3.16"]

    invalid = geo._normalize_osis("Not.A.Reference")
    assert invalid == []


def test_compose_search_terms_deduplicates_and_normalises() -> None:
    terms = geo._compose_search_terms(
        "Bethlehem",
        [
            {"name": "Bethlehem"},
            {"name": "Bethlehem Ephrathah"},
            "Bethlehem",
        ],
    )
    assert terms == ["bethlehem", "bethlehem ephrathah"]

    empty = geo._compose_search_terms("", [])
    assert empty is None


def test_parse_float_handles_various_inputs() -> None:
    assert geo._parse_float("42.5") == pytest.approx(42.5)
    assert geo._parse_float(10) == 10.0
    assert geo._parse_float(None) is None
    assert geo._parse_float("not-a-number") is None


def test_stream_json_lines_reads_objects(tmp_path: Path) -> None:
    payload = [
        {"id": 1, "name": "Bethlehem"},
        {"id": 2, "name": "Jerusalem"},
    ]
    jsonl = tmp_path / "data.jsonl"
    with jsonl.open("w", encoding="utf-8") as handle:
        for entry in payload:
            handle.write(json.dumps(entry) + "\n")

    rows = list(geo._stream_json_lines(jsonl))
    assert rows == payload

    missing = list(geo._stream_json_lines(tmp_path / "missing.jsonl"))
    assert missing == []
