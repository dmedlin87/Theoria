from __future__ import annotations

import pytest

from theo.domain.research.variants import _expand_osis, variants_apparatus


_STUB_DATASET = {
    "John.1.1": [],
    "John.1.2": [],
    "John.1.3": [],
}


@pytest.mark.parametrize(
    "osis,expected",
    [
        ("John.1.1", ["John.1.1"]),
        ("John.1.1-John.1.3", ["John.1.1", "John.1.2", "John.1.3"]),
        ("John.1.1-1.3", ["John.1.1", "John.1.2", "John.1.3"]),
    ],
)
def test_expand_osis_handles_single_and_ranges(osis: str, expected: list[str]) -> None:
    assert _expand_osis(osis, _STUB_DATASET) == expected


def test_variants_apparatus_respects_limit() -> None:
    entries = variants_apparatus("John.1.1", limit=1)
    assert len(entries) == 1
    assert entries[0].id == "john1-logos-p66"


def test_variants_apparatus_filters_categories_case_insensitively() -> None:
    entries = variants_apparatus("John.1.1", categories=["TRANSLATION"])
    assert entries
    assert {entry.category for entry in entries} == {"translation"}
