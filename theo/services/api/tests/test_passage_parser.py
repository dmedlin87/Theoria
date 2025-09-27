from __future__ import annotations

import pytest

from theo.services.api.app.ai.passage import (
    PassageResolutionError,
    resolve_passage_reference,
)


def test_resolve_passage_reference_handles_range() -> None:
    assert resolve_passage_reference("Mark 16:9–20") == "Mark.16.9-Mark.16.20"


def test_resolve_passage_reference_handles_cross_chapter() -> None:
    assert resolve_passage_reference("Mark 15:40-16:2") == "Mark.15.40-Mark.16.2"


def test_resolve_passage_reference_supports_synonyms() -> None:
    assert resolve_passage_reference("Gospel of John 3:16") == "John.3.16"


def test_resolve_passage_reference_rejects_unknown_book() -> None:
    with pytest.raises(PassageResolutionError):
        resolve_passage_reference("Unknown 1:1")
