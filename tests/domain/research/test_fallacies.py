"""Tests for heuristic fallacy detection helpers."""
from __future__ import annotations

import pytest

from theo.domain.research import fallacies as fallacies_module


def test_fallacy_detect_filters_and_sorts_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure matches respect confidence threshold and are sorted."""

    sample_dataset = [
        {
            "id": "ad_hominem",
            "name": "Ad Hominem",
            "category": "personal",
            "description": "Attacking the person instead of the argument.",
            "severity": "high",
            "keywords": ["attack the person"],
        },
        {
            "id": "strawman",
            "name": "Strawman",
            "category": "logic",
            "description": "Misrepresenting a position to refute it.",
            "severity": None,
            "keywords": ["misrepresent"],
        },
        {
            "id": "false_dilemma",
            "name": "False Dilemma",
            "category": "logic",
            "description": "Forcing a binary choice despite other options.",
            "severity": "medium",
            "keywords": ["either", "or"],
        },
    ]
    monkeypatch.setattr(fallacies_module, "fallacy_dataset", lambda: sample_dataset)

    text = "You either support us or you're misrepresenting the movement."

    hits = fallacies_module.fallacy_detect(text, min_confidence=0.3)

    assert [hit.id for hit in hits] == ["false_dilemma", "strawman"]
    assert hits[0].matches == ["either", "or"]
    assert hits[0].confidence == pytest.approx(0.6)
    assert hits[1].matches == ["misrepresent"]
    assert hits[1].confidence == pytest.approx(0.3)


def test_fallacy_detect_caps_confidence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Confidence scores should never exceed 1.0."""

    dataset = [
        {
            "id": "overconfidence",
            "name": "Overconfidence",
            "category": "logic",
            "description": "Contains many indicative phrases.",
            "severity": "low",
            "keywords": ["alpha", "beta", "gamma", "delta"],
        }
    ]
    monkeypatch.setattr(fallacies_module, "fallacy_dataset", lambda: dataset)

    hits = fallacies_module.fallacy_detect("Alpha beta gamma delta epsilon.")

    assert len(hits) == 1
    assert hits[0].matches == ["alpha", "beta", "gamma", "delta"]
    assert hits[0].confidence == pytest.approx(1.0)


def test_fallacy_detect_ignores_blank_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blank or whitespace-only input should short-circuit without dataset access."""

    def _unexpected_call() -> list[dict[str, str]]:  # pragma: no cover - defensive
        raise AssertionError("fallacy_dataset should not be called for blank text")

    monkeypatch.setattr(fallacies_module, "fallacy_dataset", _unexpected_call)

    assert fallacies_module.fallacy_detect("   \n\t  ") == []
