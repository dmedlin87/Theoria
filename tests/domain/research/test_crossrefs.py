"""Tests for the cross-reference helpers."""
from __future__ import annotations

import pytest

from theo.domain.research import crossrefs as crossrefs_module
from theo.domain.research.crossrefs import (
    CrossReferenceEntry,
    fetch_cross_references,
)


@pytest.fixture()
def stub_crossref_dataset(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[dict[str, object]]]:
    """Provide a deterministic dataset for cross-reference helpers."""

    dataset = {
        "John.3.16": [
            {
                "target": "John.3.14",
                "weight": 0.8,
                "relation_type": "theme",
                "summary": "Old Testament foreshadowing",
                "dataset": "unit-test",
            },
            {
                "target": "Numbers.21.8",
            },
            {
                "target": "Isaiah.45.22",
                "relation_type": "parallel",
            },
        ]
    }

    monkeypatch.setattr(crossrefs_module, "crossref_dataset", lambda: dataset)
    return dataset


def test_fetch_cross_references_builds_entries(
    stub_crossref_dataset: dict[str, list[dict[str, object]]]
) -> None:
    """Entries from the dataset are normalised into dataclass instances."""

    entries = fetch_cross_references("John.3.16")

    assert entries == [
        CrossReferenceEntry(
            source="John.3.16",
            target="John.3.14",
            weight=0.8,
            relation_type="theme",
            summary="Old Testament foreshadowing",
            dataset="unit-test",
        ),
        CrossReferenceEntry(
            source="John.3.16",
            target="Numbers.21.8",
            weight=None,
            relation_type=None,
            summary=None,
            dataset=None,
        ),
        CrossReferenceEntry(
            source="John.3.16",
            target="Isaiah.45.22",
            weight=None,
            relation_type="parallel",
            summary=None,
            dataset=None,
        ),
    ]


def test_fetch_cross_references_respects_limit(
    stub_crossref_dataset: dict[str, list[dict[str, object]]]
) -> None:
    """Limiting the number of cross references trims the result list."""

    entries = fetch_cross_references("John.3.16", limit=2)

    assert len(entries) == 2
    assert [entry.target for entry in entries] == [
        "John.3.14",
        "Numbers.21.8",
    ]


def test_fetch_cross_references_returns_empty_for_missing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing entries in the dataset yield an empty list."""

    monkeypatch.setattr(crossrefs_module, "crossref_dataset", lambda: {})

    assert fetch_cross_references("John.3.16") == []
