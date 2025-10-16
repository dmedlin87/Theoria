import pytest

from theo.domain.references import ScriptureReference


def test_to_range_returns_osis_when_no_bounds():
    reference = ScriptureReference("John.3.16")

    assert reference.to_range() == "John.3.16"


def test_to_range_returns_single_verse_when_bounds_match():
    reference = ScriptureReference("John.3", start_verse=16, end_verse=16)

    assert reference.to_range() == "John.3.16"


def test_to_range_handles_missing_start():
    reference = ScriptureReference("John.3", start_verse=None, end_verse=18)

    assert reference.to_range() == "John.3.?-18"


def test_to_range_handles_missing_end():
    reference = ScriptureReference("John.3", start_verse=16, end_verse=None)

    assert reference.to_range() == "John.3.16-?"


def test_to_range_handles_partial_bounds():
    reference = ScriptureReference("John.3", start_verse=16, end_verse=18)

    assert reference.to_range() == "John.3.16-18"


def test_constructor_rejects_empty_osis_id():
    with pytest.raises(ValueError):
        ScriptureReference("")
