from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.strategies import composite
from pythonbible import (
    Book,
    NormalizedReference,
    convert_reference_to_verse_ids,
    convert_verse_ids_to_references,
    get_number_of_chapters,
    get_number_of_verses,
)

from theo.services.api.app.ingest.osis import (
    DetectedOsis,
    classify_osis_matches,
    combine_references,
    detect_osis_references,
    expand_osis_reference,
    format_osis,
    osis_intersects,
    _osis_to_readable,
)


def build_reference(
    book: Book,
    start_chapter: int,
    start_verse: int,
    end_chapter: int,
    end_verse: int,
) -> NormalizedReference:
    return NormalizedReference(
        book=book,
        start_chapter=start_chapter,
        start_verse=start_verse,
        end_chapter=end_chapter,
        end_verse=end_verse,
        end_book=None,
    )


@composite
def normalized_references(draw: st.DrawFn) -> NormalizedReference:
    book = draw(st.sampled_from(list(Book)))
    max_chapter = get_number_of_chapters(book)
    start_chapter = draw(st.integers(min_value=1, max_value=max_chapter))
    start_max_verse = get_number_of_verses(book, start_chapter)
    start_verse = draw(st.integers(min_value=1, max_value=start_max_verse))

    end_chapter = draw(st.integers(min_value=start_chapter, max_value=max_chapter))
    end_min_verse = 1 if end_chapter != start_chapter else start_verse
    end_max_verse = get_number_of_verses(book, end_chapter)
    end_verse = draw(st.integers(min_value=end_min_verse, max_value=end_max_verse))

    return NormalizedReference(
        book=book,
        start_chapter=start_chapter,
        start_verse=start_verse,
        end_chapter=end_chapter,
        end_verse=end_verse,
        end_book=None,
    )


@composite
def contiguous_reference_groups(
    draw: st.DrawFn,
) -> tuple[NormalizedReference, list[NormalizedReference]]:
    reference = draw(normalized_references())
    verse_ids = list(convert_reference_to_verse_ids(reference))
    if len(verse_ids) <= 1:
        return reference, [reference]

    split_points = draw(
        st.lists(
            st.integers(min_value=1, max_value=len(verse_ids) - 1),
            unique=True,
            max_size=min(len(verse_ids) - 1, 4),
        )
    )
    split_points.sort()
    slices = [0, *split_points, len(verse_ids)]

    segments: list[NormalizedReference] = []
    for start, end in zip(slices, slices[1:]):
        segment_ids = verse_ids[start:end]
        if not segment_ids:
            continue
        segments.extend(convert_verse_ids_to_references(list(segment_ids)))

    if not segments:
        segments = [reference]
    return reference, segments


def test_format_osis_handles_single_verse_and_ranges() -> None:
    single = build_reference(Book.JOHN, 3, 16, 3, 16)
    assert format_osis(single) == "John.3.16"

    same_chapter = build_reference(Book.JOHN, 3, 16, 3, 18)
    assert format_osis(same_chapter) == "John.3.16-18"

    cross_chapter = build_reference(Book.JOHN, 3, 16, 4, 2)
    assert format_osis(cross_chapter) == "John.3.16-John.4.2"


def test_combine_references_only_merges_contiguous_ranges() -> None:
    contiguous = [
        build_reference(Book.JOHN, 3, 16, 3, 17),
        build_reference(Book.JOHN, 3, 18, 3, 18),
    ]
    combined = combine_references(contiguous)
    assert combined is not None
    assert format_osis(combined) == "John.3.16-18"

    disjoint = [
        build_reference(Book.JOHN, 3, 16, 3, 17),
        build_reference(Book.JOHN, 3, 20, 3, 21),
    ]
    assert combine_references(disjoint) is None


def test_osis_to_readable_covers_varied_inputs() -> None:
    assert _osis_to_readable("John.3.16") == "John 3:16"
    assert _osis_to_readable("John.3.16-18") == "John 3:16-18"
    assert _osis_to_readable("John.3.16-John.4.2") == "John 3:16-4:2"
    assert _osis_to_readable("Gen.1.1-Exod.2.3") == "Gen 1:1-Exod 2:3"
    assert _osis_to_readable("Gen.1-Exod.2.3") == "Gen 1-Exod 2:3"


def test_expand_osis_reference_matches_pythonbible_conversion() -> None:
    reference = "John.3.16-18"
    expected = frozenset(
        convert_reference_to_verse_ids(build_reference(Book.JOHN, 3, 16, 3, 18))
    )
    assert expand_osis_reference(reference) == expected

    assert expand_osis_reference("invalid") == frozenset()


def test_osis_intersects_handles_overlap_and_mismatches() -> None:
    assert osis_intersects("John.3.16-18", "John.3.17")
    assert not osis_intersects("John.3.16-18", "John.4.1")
    assert not osis_intersects("invalid", "John.3.16")


def test_classify_osis_matches_partitions_and_deduplicates() -> None:
    detected = ["John.3.16-18"]
    hints = ["John.3.16", "Luke.1.1", "John.3.16", ""]
    matched, unmatched = classify_osis_matches(detected, hints)
    assert matched == ["John.3.16"]
    assert unmatched == ["Luke.1.1"]


def test_detect_osis_references_combines_primary() -> None:
    detected = detect_osis_references("John 3:16-18")
    assert isinstance(detected, DetectedOsis)
    assert detected.primary == "John.3.16-18"
    assert detected.all == ["John.3.16-18"]

    empty = detect_osis_references("no scripture here")
    assert empty == DetectedOsis(primary=None, all=[])


@given(normalized_references())
@settings(max_examples=40)
def test_expand_roundtrip_matches_pythonbible(reference: NormalizedReference) -> None:
    osis_value = format_osis(reference)
    expected_ids = frozenset(convert_reference_to_verse_ids(reference))
    assert expand_osis_reference(osis_value) == expected_ids


@given(contiguous_reference_groups())
@settings(max_examples=40)
def test_combine_references_stabilises_contiguous_sequences(
    data: tuple[NormalizedReference, list[NormalizedReference]]
) -> None:
    reference, segments = data
    combined = combine_references(segments)
    expected_ids = tuple(convert_reference_to_verse_ids(reference))
    if combined is not None:
        assert tuple(convert_reference_to_verse_ids(combined)) == expected_ids
    else:
        flattened = []
        for segment in segments:
            flattened.extend(convert_reference_to_verse_ids(segment))
        assert tuple(sorted(flattened)) == expected_ids


@given(normalized_references())
@settings(max_examples=25)
def test_detect_references_from_human_readable_round_trip(
    reference: NormalizedReference,
) -> None:
    osis_value = format_osis(reference)
    readable = _osis_to_readable(osis_value)
    detected = detect_osis_references(readable)
    assert osis_value in detected.all
    if detected.primary:
        expanded_primary = expand_osis_reference(detected.primary)
        assert expand_osis_reference(osis_value).issubset(expanded_primary)
