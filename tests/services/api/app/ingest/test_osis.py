from __future__ import annotations

from textwrap import dedent

import pytest
from pythonbible import Book, NormalizedReference

from theo.services.api.app.ingest import osis


def _make_reference(book: Book, start: int, end: int | None = None) -> NormalizedReference:
    end_verse = end if end is not None else start
    return NormalizedReference(
        book=book,
        start_chapter=1,
        start_verse=start,
        end_chapter=1,
        end_verse=end_verse,
        end_book=None,
    )


def test_parse_osis_document_extracts_metadata() -> None:
    xml = dedent(
        """
        <osis xmlns:xml="http://www.w3.org/XML/1998/namespace">
          <osisText osisIDWork="sample.work">
            <header>
              <work osisWork="sample.work">
                <title>Document Title</title>
              </work>
            </header>
            <div type="book">
              <chapter osisID="Gen.1">
                <verse osisID="Gen.1.1">In the beginning</verse>
                <verse osisRef="Gen.1.2 Gen.1.3">Second verse</verse>
                <note type="commentary" osisID="note-1" osisRef="Gen.1.1 Gen.1.2 Gen.1.2">
                  <title>Commentary Title</title>
                  Commentary text.
                </note>
              </chapter>
            </div>
          </osisText>
        </osis>
        """
    ).strip()

    document = osis.parse_osis_document(xml)

    assert document.work == "sample.work"
    assert document.title == "Document Title"
    assert [verse.osis_id for verse in document.verses] == [
        "Gen.1.1",
        "Gen.1.2",
        "Gen.1.3",
    ]
    assert document.verses[0].text == "In the beginning"
    # Commentary anchors are deduplicated and only valid OSIS identifiers survive.
    assert document.commentaries == []


@pytest.mark.parametrize(
    "raw,expected",
    [
        (" Gen.1.1 ", "Gen.1.1"),
        ("Gen.1.1!note-1", "Gen.1.1"),
        ("", None),
    ],
)
def test_canonicalize_osis_id_normalises_and_filters(raw: str, expected: str | None) -> None:
    assert osis.canonicalize_osis_id(raw) == expected


def test_canonicalize_osis_id_handles_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(osis, "expand_osis_reference", lambda _value: (_ for _ in ()).throw(ValueError("boom")))

    assert osis.canonicalize_osis_id("Gen.1.1") is None


def test_combine_references_merges_contiguous_ranges() -> None:
    refs = [_make_reference(Book.GENESIS, 1), _make_reference(Book.GENESIS, 2)]

    merged = osis.combine_references(refs)

    assert merged is not None
    assert merged.book == Book.GENESIS
    assert merged.start_verse == 1
    assert merged.end_verse == 2


def test_combine_references_rejects_gaps_or_mixed_books() -> None:
    gap_refs = [_make_reference(Book.GENESIS, 1), _make_reference(Book.GENESIS, 3)]
    mixed_refs = [_make_reference(Book.GENESIS, 1), _make_reference(Book.EXODUS, 1)]

    assert osis.combine_references(gap_refs) is None
    assert osis.combine_references(mixed_refs) is mixed_refs[0]


def test_detect_osis_references_returns_primary_range() -> None:
    detected = osis.detect_osis_references("See Gen 1:1 and Gen 1:2 together.")

    assert detected.primary == "Gen.1.1-2"
    assert detected.all == ["Gen.1.1", "Gen.1.2"]


def test_canonical_verse_range_handles_duplicates_and_invalid() -> None:
    references = ["Gen.1.1", "Gen.1.2", "Gen.1.2", "not-a-ref"]

    verse_ids, start, end = osis.canonical_verse_range(references)

    assert verse_ids == [1001001, 1001002]
    assert start == 1001001
    assert end == 1001002


def test_osis_intersects_and_classify_matches() -> None:
    assert osis.osis_intersects("Gen.1.1", "Gen.1.1-Gen.1.2") is True
    assert osis.osis_intersects("Gen.1.1", "Gen.1.3") is False

    matched, unmatched = osis.classify_osis_matches(
        detected=["Gen.1.1-Gen.1.2", ""],
        hints=["Gen.1.2", "Gen.1.3", ""],
    )

    assert matched == ["Gen.1.2"]
    assert unmatched == ["Gen.1.3"]
