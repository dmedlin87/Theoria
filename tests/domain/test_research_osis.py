import pytest

from pythonbible import convert_reference_to_verse_ids, get_references

from theo.domain.research import osis as research_osis


@pytest.mark.parametrize(
    "osis, expected",
    [
        ("Gen.1", "Gen 1"),
        ("Gen.1.1", "Gen 1:1"),
        ("Gen.1.1-3", "Gen 1:1-3"),
        ("Gen.1.1-Gen.2.3", "Gen 1:1-2:3"),
        ("Gen.1-Exod.2.3", "Gen 1-Exod 2:3"),
        ("Gen.1-Exod", "Gen 1-Exod"),
        ("Gen.1.1-Exod.2", "Gen 1:1-Exod 2"),
    ],
)
def test_osis_to_readable_formats_ranges(osis: str, expected: str) -> None:
    """The conversion helper should format a variety of OSIS ranges."""

    assert research_osis.osis_to_readable(osis) == expected


def test_osis_to_readable_rejects_empty_reference() -> None:
    """Invalid references should raise a ``ValueError``."""

    with pytest.raises(ValueError):
        research_osis.osis_to_readable("-Invalid")


@pytest.mark.parametrize(
    "osis, expected",
    [
        ("John.3.16", ["John.3.16"]),
        ("John.3.16-17", ["John.3.16-17"]),
        ("John.3.16-John.3.18", ["John.3.16-18"]),
    ],
)
def test_format_osis_roundtrip_with_pythonbible(osis: str, expected: list[str]) -> None:
    """Formatting should round-trip with pythonbible normalization."""

    references = get_references(research_osis.osis_to_readable(osis))
    formatted = [research_osis.format_osis(ref) for ref in references]

    assert formatted == expected


def test_expand_osis_reference_handles_invalid_input() -> None:
    """Invalid OSIS strings should fall back to an empty set."""

    research_osis.expand_osis_reference.cache_clear()

    assert research_osis.expand_osis_reference("NotARealReference") == frozenset()


@pytest.mark.parametrize(
    "osis",
    [
        "John.3.16",
        "John.3.16-17",
    ],
)
def test_expand_osis_reference_returns_expected_verse_ids(osis: str) -> None:
    """Valid OSIS strings should expand to the expected verse identifiers."""

    research_osis.expand_osis_reference.cache_clear()

    expected: set[int] = set()
    for reference in get_references(research_osis.osis_to_readable(osis)):
        expected.update(convert_reference_to_verse_ids(reference))

    assert research_osis.expand_osis_reference(osis) == expected


def test_expand_osis_reference_recovers_from_conversion_error(monkeypatch) -> None:
    """Errors converting a normalized reference should be handled gracefully."""

    class BadReference:
        """Simple placeholder that lacks pythonbible attributes."""

        pass

    monkeypatch.setattr(
        research_osis.pb,
        "get_references",
        lambda _: [BadReference()],
    )

    research_osis.expand_osis_reference.cache_clear()

    assert research_osis.expand_osis_reference("John.3.16") == frozenset()


def test_verse_ids_to_osis_matches_formatting() -> None:
    """Iterating through verse identifiers should mirror the formatting helper."""

    research_osis.expand_osis_reference.cache_clear()

    references = get_references("John 3:16-17")
    verse_ids: set[int] = set()
    for reference in references:
        verse_ids.update(convert_reference_to_verse_ids(reference))

    assert list(research_osis.verse_ids_to_osis(sorted(verse_ids))) == [
        "John.3.16",
        "John.3.17",
    ]
