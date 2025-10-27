"""Property-based tests for OSIS parsing and chunking heuristics."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st
import pythonbible as pb

from theo.infrastructure.api.app.ingest.chunking import Chunk, chunk_text
from theo.infrastructure.api.app.ingest.osis import (
    DetectedOsis,
    combine_references,
    detect_osis_references,
    expand_osis_reference,
    format_osis,
    _osis_to_readable,
)


HYPOTHESIS_SETTINGS = settings(max_examples=40, deadline=None)

@st.composite
def normalized_references(draw) -> pb.NormalizedReference:
    """Generate valid pythonbible ``NormalizedReference`` instances."""

    book = draw(st.sampled_from(list(pb.Book)))
    chapter_count = pb.get_number_of_chapters(book)
    start_chapter = draw(st.integers(min_value=1, max_value=chapter_count))
    start_verse = draw(
        st.integers(
            min_value=1,
            max_value=pb.get_number_of_verses(book, start_chapter),
        )
    )
    end_chapter = draw(
        st.integers(min_value=start_chapter, max_value=chapter_count)
    )
    end_verse = draw(
        st.integers(
            min_value=(start_verse if end_chapter == start_chapter else 1),
            max_value=pb.get_number_of_verses(book, end_chapter),
        )
    )
    return pb.NormalizedReference(
        book=book,
        start_chapter=start_chapter,
        start_verse=start_verse,
        end_chapter=end_chapter,
        end_verse=end_verse,
        end_book=None,
    )


@st.composite
def paragraph_texts(draw) -> str:
    """Compose realistic multi-paragraph text samples."""

    word = st.text(alphabet=st.characters(whitelist_categories=("Ll", "Lu")), min_size=1, max_size=8)
    sentence = st.lists(word, min_size=3, max_size=12).map(
        lambda words: (words[0].capitalize() + " " + " ".join(words[1:])).strip() + "."
    )
    paragraph = st.lists(sentence, min_size=1, max_size=5).map(" ".join)
    paragraphs = draw(st.lists(paragraph, min_size=1, max_size=6))
    # Introduce variable padding around paragraphs to exercise offset logic.
    spaced_paragraphs: list[str] = []
    for entry in paragraphs:
        prefix = draw(st.text(alphabet=" \t", max_size=2))
        suffix = draw(st.text(alphabet=" \t", max_size=2))
        spaced_paragraphs.append(f"{prefix}{entry}{suffix}")
    return "\n\n".join(spaced_paragraphs)


@HYPOTHESIS_SETTINGS
@given(normalized_references())
def test_detect_osis_round_trip(reference: pb.NormalizedReference) -> None:
    """Formatting then detecting an OSIS reference should be lossless."""

    osis_value = format_osis(reference)
    # Embed the generated reference in noisy prose to verify detection robustness.
    readable = _osis_to_readable(osis_value)
    text_value = f"Lecture notes mention {readable} alongside supplementary remarks."
    detected = detect_osis_references(text_value)

    assert isinstance(detected, DetectedOsis)
    assert osis_value in detected.all
    assert detected.primary is not None

    expected_ids = set(pb.convert_reference_to_verse_ids(reference))
    primary_ids = expand_osis_reference(detected.primary)
    assert primary_ids.issuperset(expected_ids)


@HYPOTHESIS_SETTINGS
@given(st.lists(normalized_references(), min_size=1, max_size=4))
def test_combine_references_matches_detected_primary(
    references: list[pb.NormalizedReference],
) -> None:
    """``combine_references`` should mirror detection's primary range logic."""

    combined = combine_references(references)
    osis_values = [format_osis(ref) for ref in references]
    readable_values = [_osis_to_readable(value) for value in osis_values]
    text_value = "; ".join(readable_values)
    detected = detect_osis_references(text_value)

    if combined is None:
        # If the references cannot be merged, the primary should still be a member.
        assert detected.primary in osis_values
        return

    assert detected.primary == format_osis(combined)


@HYPOTHESIS_SETTINGS
@given(paragraph_texts(), st.integers(min_value=120, max_value=240))
def test_chunk_text_preserves_offsets_and_token_budgets(
    text: str, max_tokens: int
) -> None:
    """Chunking heuristics maintain offsets and respect configured budgets."""

    min_tokens = max(40, max_tokens // 3)
    hard_cap = max_tokens + 60

    chunks = chunk_text(
        text,
        max_tokens=max_tokens,
        min_tokens=min_tokens,
        hard_cap=hard_cap,
    )

    assert chunks, "At least one chunk should be produced"

    normalised_original = [part.strip() for part in text.split("\n\n") if part.strip()]
    reconstructed = "\n\n".join(chunk.text for chunk in chunks)
    assert reconstructed == "\n\n".join(normalised_original)

    last_end = 0
    seen_indices: set[int] = set()
    for chunk in chunks:
        assert isinstance(chunk, Chunk)
        assert chunk.index is not None
        assert chunk.index not in seen_indices
        seen_indices.add(chunk.index)
        assert chunk.index >= 0
        assert chunk.start_char <= chunk.end_char
        assert chunk.start_char >= last_end
        original_slice = text[chunk.start_char : chunk.end_char]
        sanitised_slice = "\n\n".join(
            segment.strip() for segment in original_slice.split("\n\n")
        )
        assert sanitised_slice == chunk.text
        token_count = len(chunk.text.split())
        assert token_count <= hard_cap
        last_end = chunk.end_char

