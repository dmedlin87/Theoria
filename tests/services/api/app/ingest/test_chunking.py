from __future__ import annotations

from theo.services.api.app.ingest.chunking import chunk_text, chunk_transcript
from theo.services.api.app.ingest.parsers import TranscriptSegment


def test_chunk_text_respects_token_budgets_and_indexes() -> None:
    text = (
        "First paragraph words here.\n\nSecond block has more words. Another piece ensures flushing."
        "\n\nThird section closes out."
    )

    chunks = chunk_text(
        text,
        max_tokens=5,
        min_tokens=3,
        hard_cap=6,
    )

    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    assert chunks[0].text.startswith("First paragraph")
    assert any("Second block" in chunk.text for chunk in chunks)
    assert chunks[-1].text.startswith("Third section")
    # Each chunk should stay within the hard cap once tokenised.
    for chunk in chunks:
        assert len(chunk.text.split()) <= 6


def test_chunk_text_splits_overlong_paragraphs_on_sentence_boundaries() -> None:
    text = (
        "Sentence one is here. Sentence two follows closely! Sentence three wraps up the paragraph."
    )

    chunks = chunk_text(
        text,
        max_tokens=10,
        min_tokens=3,
        hard_cap=5,
    )

    assert len(chunks) == 3
    assert chunks[0].text.endswith("here.")
    assert chunks[1].text.endswith("closely!")
    assert chunks[2].text.endswith("paragraph.")


def test_chunk_transcript_flushes_on_time_window_and_preserves_metadata() -> None:
    segments = [
        TranscriptSegment(text="alpha beta", start=0.0, end=5.0, speaker="Alice"),
        TranscriptSegment(text="gamma delta", start=5.5, end=9.5, speaker="Bob"),
        TranscriptSegment(text="epsilon zeta eta", start=9.6, end=11.0, speaker="Alice"),
    ]

    chunks = chunk_transcript(
        segments,
        max_tokens=4,
        hard_cap=6,
        max_window_seconds=6.0,
    )

    assert len(chunks) == 2
    first, second = chunks
    assert first.t_start == 0.0 and first.t_end == 5.0
    assert second.t_start == 5.5 and second.t_end == 11.0
    # Speakers should be aggregated and deduplicated in sorted order.
    assert first.speakers == ["Alice"]
    assert second.speakers == ["Alice", "Bob"]
    # Chunks keep monotonically increasing indexes and char positions.
    assert first.index == 0
    assert second.index == 1
    assert second.start_char > first.end_char
