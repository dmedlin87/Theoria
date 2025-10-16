"""Tests for Dead Sea Scroll linkage helpers."""
from __future__ import annotations

import pytest

from theo.domain.research import dss_links
from theo.domain.research.dss_links import DssLinkEntry, fetch_dss_links, _expand_osis


@pytest.mark.parametrize(
    "osis,expected",
    [
        ("John.3.16", ["John.3.16"]),
        (
            "John.3.16-John.3.18",
            ["John.3.16", "John.3.17", "John.3.18"],
        ),
        (
            "John.3.16-18",
            ["John.3.16", "John.3.17", "John.3.18"],
        ),
        (
            "John.3.18-16",
            ["John.3.16", "John.3.17", "John.3.18"],
        ),
    ],
)
def test_expand_osis_handles_single_and_range_inputs(osis: str, expected: list[str]) -> None:
    """Verify `_expand_osis` expands single verses and simple ranges."""
    assert _expand_osis(osis) == expected


def test_expand_osis_returns_original_bounds_for_invalid_range() -> None:
    """Invalid ranges fall back to the original bounds."""
    assert _expand_osis("John.3.bad-18") == ["John.3.bad", "John.3.18"]


def test_fetch_dss_links_normalises_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    """`fetch_dss_links` cleans and enriches raw dataset entries."""
    dataset = {
        "John.3.16": [
            {
                "id": "explicit-id",
                "osis": "John.3.16",
                "title": "Existing title",
                "fragment": "Unused fragment",
                "url": "https://example.com/16",
                "summary": "summary",
                "dataset": "unit",
            }
        ],
        "John.3.17": [
            {
                "fragment": "Fragment title",
                "url": "https://example.com/17",
            }
        ],
        "John.3.18": [
            {
                "url": "https://example.com/18",
            },
            {
                "url": None,
                "title": "Should be ignored",
            },
        ],
    }

    monkeypatch.setattr(dss_links, "dss_links_dataset", lambda: dataset)

    entries = fetch_dss_links("John.3.16-18")

    assert [entry.osis for entry in entries] == ["John.3.16", "John.3.17", "John.3.18"]

    first, second, third = entries

    assert isinstance(first, DssLinkEntry)
    assert first.id == "explicit-id"
    assert first.title == "Existing title"
    assert first.summary == "summary"
    assert first.dataset == "unit"

    assert second.id == "John.3.17:1"
    assert second.osis == "John.3.17"
    assert second.title == "Fragment title"
    assert second.summary is None

    assert third.id == "John.3.18:2"
    assert third.title == "Dead Sea Scrolls link"
    assert third.fragment is None

    assert len(entries) == 3
