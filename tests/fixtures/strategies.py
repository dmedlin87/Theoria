"""Shared Hypothesis strategies for ingestion property tests."""

from __future__ import annotations

import string
import sys
import types

import pythonbible as pb
from pythonbible import NormalizedReference
from hypothesis import settings, strategies as st

if "fastapi" not in sys.modules:
    fastapi_module = types.ModuleType("fastapi")
    status_module = types.SimpleNamespace(HTTP_422_UNPROCESSABLE_CONTENT=422)
    fastapi_module.status = status_module  # type: ignore[attr-defined]
    sys.modules["fastapi"] = fastapi_module
    sys.modules["fastapi.status"] = status_module

if "pypdf" not in sys.modules:
    pypdf_module = types.ModuleType("pypdf")
    errors_module = types.ModuleType("pypdf.errors")
    class FileNotDecryptedError(RuntimeError):
        pass
    class PdfReadError(RuntimeError):
        pass
    errors_module.FileNotDecryptedError = FileNotDecryptedError  # type: ignore[attr-defined]
    errors_module.PdfReadError = PdfReadError  # type: ignore[attr-defined]
    class DummyPdfReader:
        pass
    pypdf_module.PdfReader = DummyPdfReader  # type: ignore[attr-defined]
    pypdf_module.errors = errors_module  # type: ignore[attr-defined]
    sys.modules["pypdf"] = pypdf_module
    sys.modules["pypdf.errors"] = errors_module

from theo.domain.research.osis import format_osis
from theo.infrastructure.api.app.ingest.parsers import TranscriptSegment

__all__ = [
    "DEFAULT_HYPOTHESIS_SETTINGS",
    "normalized_osis_references",
    "osis_reference_strings",
    "text_documents",
    "transcript_segments",
]

DEFAULT_HYPOTHESIS_SETTINGS = settings(
    max_examples=40, deadline=None, derandomize=True
)

_WORD_ALPHABET = string.ascii_letters + "'-"
_SPEAKER_ALPHABET = string.ascii_letters + " .-"


def _word_strategy(min_size: int = 1, max_size: int = 10) -> st.SearchStrategy[str]:
    return st.text(alphabet=_WORD_ALPHABET, min_size=min_size, max_size=max_size)


@st.composite
def normalized_osis_references(draw) -> NormalizedReference:
    """Generate contiguous pythonbible ``NormalizedReference`` ranges."""

    book = draw(st.sampled_from([book for book in pb.Book]))
    chapter_count = pb.get_number_of_chapters(book)
    start_chapter = draw(st.integers(min_value=1, max_value=chapter_count))
    start_verse = draw(
        st.integers(
            min_value=1,
            max_value=pb.get_number_of_verses(book, start_chapter),
        )
    )
    max_end_chapter = min(chapter_count, start_chapter + 3)
    end_chapter = draw(
        st.integers(min_value=start_chapter, max_value=max_end_chapter)
    )
    end_verse_min = start_verse if end_chapter == start_chapter else 1
    end_verse = draw(
        st.integers(
            min_value=end_verse_min,
            max_value=pb.get_number_of_verses(book, end_chapter),
        )
    )
    end_book = None if (end_chapter == start_chapter and end_verse == start_verse) else book
    return NormalizedReference(
        book=book,
        start_chapter=start_chapter,
        start_verse=start_verse,
        end_chapter=end_chapter,
        end_verse=end_verse,
        end_book=end_book,
    )


def osis_reference_strings() -> st.SearchStrategy[str]:
    """Return OSIS reference strings derived from normalized references."""

    return normalized_osis_references().map(format_osis)


def text_documents(
    *, min_paragraphs: int = 1, max_paragraphs: int = 6
) -> st.SearchStrategy[str]:
    """Compose multi-paragraph documents with realistic spacing."""

    sentence = st.lists(
        _word_strategy(min_size=1, max_size=8), min_size=3, max_size=12
    ).map(lambda words: " ".join(words).strip().capitalize() + ".")
    paragraph = st.lists(sentence, min_size=1, max_size=5).map(" ".join)
    paragraphs = st.lists(paragraph, min_size=min_paragraphs, max_size=max_paragraphs)

    return st.one_of(
        st.just(""),
        paragraphs.map(lambda entries: "\n\n".join(entry.strip() for entry in entries)),
        paragraphs.map(
            lambda entries: "\n\n".join(
                entry if entry.endswith((".", "!", "?")) else f"{entry}."
                for entry in entries
            )
        ),
    )


@st.composite
def transcript_segments(
    draw,
    *,
    min_segments: int = 1,
    max_segments: int = 6,
    max_gap: float = 3.0,
) -> list[TranscriptSegment]:
    """Generate ordered transcript segments with bounded durations."""

    count = draw(st.integers(min_value=min_segments, max_value=max_segments))
    start_time = draw(st.floats(min_value=0.0, max_value=60.0, allow_nan=False))
    segments: list[TranscriptSegment] = []
    current_start = start_time

    for _ in range(count):
        duration = draw(
            st.floats(min_value=0.25, max_value=10.0, allow_nan=False, allow_infinity=False)
        )
        end_time = current_start + duration
        text = draw(
            st.lists(_word_strategy(min_size=1, max_size=10), min_size=3, max_size=15).map(
                lambda words: " ".join(words)
            )
        )
        speaker = draw(
            st.one_of(
                st.none(),
                st.text(alphabet=_SPEAKER_ALPHABET, min_size=3, max_size=16),
            )
        )
        segments.append(
            TranscriptSegment(text=text, start=current_start, end=end_time, speaker=speaker)
        )
        gap = draw(st.floats(min_value=0.0, max_value=max_gap, allow_nan=False))
        current_start = end_time + gap

    return segments
