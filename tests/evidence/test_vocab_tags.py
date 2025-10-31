"""Tests covering evidence card vocabulary normalisation."""

import pytest

try:
    from theo.infrastructure.api.app.research.evidence_cards import _normalize_tags
except ModuleNotFoundError as exc:  # pragma: no cover - dependency missing in CI
    pytest.skip(f"dependency not available: {exc}", allow_module_level=True)
except ImportError as exc:  # pragma: no cover - dependency missing in CI
    pytest.skip(f"dependency not available: {exc}", allow_module_level=True)


def test_normalize_tags_deduplicates_and_sorts_case_insensitive() -> None:
    tags = ["  Faith ", "FAITH", "context", None, "  context", "  "]

    normalised = _normalize_tags(tags)

    assert normalised == ["Faith", "context"]


def test_normalize_tags_returns_none_for_empty_values() -> None:
    assert _normalize_tags(["  ", None]) is None
