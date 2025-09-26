"""Tests for OSIS detection utilities."""

from theo.services.api.app.ingest.osis import (
    detect_osis_references,
    expand_osis_reference,
    osis_intersects,
)


def test_detects_range_and_primary() -> None:
    text = "In the beginning was the Word (John 1:1-5) and the Word was with God."
    detected = detect_osis_references(text)

    assert detected.primary == "John.1.1-5"
    assert "John.1.1-5" in detected.all


def test_osis_intersection_logic() -> None:
    assert osis_intersects("John.1.1-5", "John.1.3")
    assert osis_intersects("John.1.1-5", "John.1.1-2")
    assert not osis_intersects("John.1.1", "John.2.1")


def test_non_contiguous_references_do_not_merge() -> None:
    text = "References to John 1:1 and John 1:3 are not contiguous."

    detected = detect_osis_references(text)

    assert detected.primary == "John.1.1"
    assert detected.all == ["John.1.1", "John.1.3"]


def test_expand_reference_is_cached() -> None:
    expand_osis_reference.cache_clear()

    initial_info = expand_osis_reference.cache_info()
    assert initial_info.hits == 0
    assert initial_info.misses == 0

    first = expand_osis_reference("John.1.1-5")
    assert isinstance(first, frozenset)

    after_first = expand_osis_reference.cache_info()
    assert after_first.hits == 0
    assert after_first.misses == 1

    second = expand_osis_reference("John.1.1-5")
    assert second == first

    after_second = expand_osis_reference.cache_info()
    assert after_second.hits == 1
    assert after_second.misses == 1
