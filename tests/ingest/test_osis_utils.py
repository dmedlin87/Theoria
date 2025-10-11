from __future__ import annotations

from pythonbible import Book, NormalizedReference, convert_reference_to_verse_ids

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
