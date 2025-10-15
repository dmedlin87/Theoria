"""Tests for the historicity search helpers."""

from __future__ import annotations

import pytest

from theo.domain.research import historicity as historicity_module
from theo.domain.research.historicity import historicity_search


@pytest.fixture()
def stub_historicity_dataset(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Provide a deterministic dataset for the historicity search helpers."""

    dataset = [
        {
            "id": "entry-1",
            "title": "Early Census Studies",
            "authors": ["Sean E. Bond"],
            "year": 2011,
            "summary": "Overview of inscriptional evidence.",
            "tags": ["census", "history"],
            "source": "Journal",  # Optional field that should be ignored by the scorer.
        },
        {
            "id": "entry-2",
            "title": "Bethlehem Archaeology",
            "authors": ["Elaine Pritchard"],
            "year": 2018,
            "summary": "Herodian era survey findings.",
            "tags": ["archaeology"],
        },
    ]

    monkeypatch.setattr(historicity_module, "historicity_dataset", lambda: dataset)
    return dataset


def test_historicity_search_matches_author_tokens(
    stub_historicity_dataset: list[dict[str, object]]
) -> None:
    """Author names should contribute to the ranking score."""

    results = historicity_search("Bond")
    assert [entry.id for entry in results] == ["entry-1"]


def test_historicity_search_filters_empty_queries(
    stub_historicity_dataset: list[dict[str, object]]
) -> None:
    """Whitespace-only searches should return no results."""

    assert historicity_search("   ") == []
