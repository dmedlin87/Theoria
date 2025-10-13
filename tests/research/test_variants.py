"""Tests for the textual variants apparatus helpers."""
from __future__ import annotations

import pytest

from theo.domain.research import variants as variants_module
from theo.domain.research.variants import variants_apparatus


@pytest.fixture
def stub_variants_dataset(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[dict[str, object]]]:
    """Provide a deterministic dataset for apparatus queries."""

    dataset = {
        "John.1.1": [
            {"id": "j1", "category": "variant", "reading": "v1"},
            {"id": "j1-note", "category": "note", "reading": "n1"},
        ],
        "John.1.2": [
            {"id": "j2", "category": "variant", "reading": "v2"},
        ],
        "John.1.3": [
            {"id": "j3", "category": "other", "reading": "o3"},
        ],
    }

    monkeypatch.setattr(variants_module, "variants_dataset", lambda: dataset)
    return dataset


def test_variants_apparatus_expands_ranges(stub_variants_dataset: dict[str, list[dict[str, object]]]) -> None:
    readings = variants_apparatus("John.1.1-3")

    assert [entry.osis for entry in readings] == [
        "John.1.1",
        "John.1.1",
        "John.1.2",
        "John.1.3",
    ]


def test_variants_apparatus_applies_category_filters(
    stub_variants_dataset: dict[str, list[dict[str, object]]]
) -> None:
    readings = variants_apparatus("John.1.1-3", categories=["variant"])

    assert [entry.id for entry in readings] == ["j1", "j2"]
    assert {entry.category for entry in readings} == {"variant"}


def test_variants_apparatus_respects_limit(
    stub_variants_dataset: dict[str, list[dict[str, object]]]
) -> None:
    readings = variants_apparatus("John.1.1-3", limit=2)

    assert len(readings) == 2
    assert [entry.id for entry in readings] == ["j1", "j1-note"]
