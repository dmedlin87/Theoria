"""Tests for OSIS detection utilities."""

from theo.services.api.app.ingest.osis import detect_osis_references, osis_intersects


def test_detects_range_and_primary() -> None:
    text = "In the beginning was the Word (John 1:1-5) and the Word was with God."
    detected = detect_osis_references(text)

    assert detected.primary == "John.1.1-5"
    assert "John.1.1-5" in detected.all


def test_osis_intersection_logic() -> None:
    assert osis_intersects("John.1.1-5", "John.1.3")
    assert osis_intersects("John.1.1-5", "John.1.1-2")
    assert not osis_intersects("John.1.1", "John.2.1")
