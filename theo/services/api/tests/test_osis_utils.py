from types import SimpleNamespace

import pytest

from theo.services.api.app.core.database import get_engine
from theo.services.api.app.ingest.osis import _osis_to_readable, osis_intersects
from theo.services.api.app.transcripts.service import _matches_osis



@pytest.fixture(autouse=True)
def dispose_engine() -> None:
    try:
        yield
    finally:
        get_engine().dispose()

@pytest.mark.parametrize(
    "reference, expected",
    [
        ("John.1", "John 1"),
        ("John.1.1-1.5", "John 1:1-5"),
        ("John.1-John.2", "John 1-2"),
    ],
)
def test_osis_to_readable_normalizes_inputs(reference: str, expected: str) -> None:
    assert _osis_to_readable(reference) == expected


def test_matches_osis_accepts_chapter_only_query() -> None:
    segment = SimpleNamespace(primary_osis="John.1.1", osis_refs=["John.1.2"], text="")
    assert _matches_osis(segment, "John.1")


def test_osis_intersects_handles_chapter_range() -> None:
    assert osis_intersects("John.1", "John.1.3-1.4")
