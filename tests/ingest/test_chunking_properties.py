"""Property tests covering chunking heuristics for text and transcripts."""

from __future__ import annotations

import importlib
import sys
import types

import pytest
from hypothesis import given

from tests.fixtures.strategies import (
    DEFAULT_HYPOTHESIS_SETTINGS,
    text_documents,
    transcript_segments,
)

if "fastapi" not in sys.modules:
    fastapi_module = types.ModuleType("fastapi")
    status_module = types.SimpleNamespace(HTTP_422_UNPROCESSABLE_ENTITY=422)
    fastapi_module.status = status_module  # type: ignore[attr-defined]
    sys.modules["fastapi"] = fastapi_module
    sys.modules["fastapi.status"] = status_module

legacy_services = importlib.import_module("theo.services")
chunking_module = importlib.import_module("theo.infrastructure.api.app.ingest.chunking")


def _register_legacy_submodule(name: str, module: types.ModuleType) -> None:
    """Expose *module* under ``theo.services.api.app.ingest`` for compatibility."""

    api_pkg = getattr(legacy_services, "api", None)
    if api_pkg is None:
        api_pkg = types.ModuleType("theo.services.api")
        api_pkg.__path__ = []  # type: ignore[attr-defined]
        setattr(legacy_services, "api", api_pkg)
        sys.modules["theo.services.api"] = api_pkg
    app_pkg = getattr(api_pkg, "app", None)
    if app_pkg is None:
        app_pkg = types.ModuleType("theo.services.api.app")
        app_pkg.__path__ = []  # type: ignore[attr-defined]
        setattr(api_pkg, "app", app_pkg)
        sys.modules["theo.services.api.app"] = app_pkg
    ingest_pkg = getattr(app_pkg, "ingest", None)
    if ingest_pkg is None:
        ingest_pkg = types.ModuleType("theo.services.api.app.ingest")
        ingest_pkg.__path__ = []  # type: ignore[attr-defined]
        setattr(app_pkg, "ingest", ingest_pkg)
        sys.modules["theo.services.api.app.ingest"] = ingest_pkg

    setattr(ingest_pkg, name, module)
    sys.modules[f"theo.services.api.app.ingest.{name}"] = module


_register_legacy_submodule("chunking", chunking_module)

from theo.services.api.app.ingest import chunking as legacy_chunking  # noqa: E402


@given(text_documents())
@DEFAULT_HYPOTHESIS_SETTINGS
def test_chunk_text_respects_indices_and_token_caps(text: str) -> None:
    """Chunked passages preserve offsets and never exceed configured caps."""

    chunks = legacy_chunking.chunk_text(
        text, max_tokens=80, min_tokens=40, hard_cap=120
    )

    assert chunks, "Chunking should always emit at least one chunk"
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))

    last_end = 0
    for chunk in chunks:
        assert chunk.index is not None
        assert chunk.start_char >= last_end
        assert chunk.start_char <= chunk.end_char
        assert chunk.end_char <= len(text) if text else chunk.end_char == 0

        original_slice = text[chunk.start_char : chunk.end_char]
        normalized = "\n\n".join(
            segment.strip() for segment in original_slice.split("\n\n") if segment.strip()
        )
        if chunk.text:
            assert chunk.text == normalized

        token_count = len(chunk.text.split())
        assert token_count <= 120
        last_end = chunk.end_char


@given(transcript_segments())
@DEFAULT_HYPOTHESIS_SETTINGS
def test_chunk_transcript_respects_overlaps_and_temporal_window(
    segments: list
) -> None:
    """Transcript chunking preserves ordering and speaker metadata."""

    chunks = legacy_chunking.chunk_transcript(
        segments,
        max_tokens=60,
        hard_cap=90,
        max_window_seconds=25.0,
    )

    assert chunks, "Transcript chunking should return at least one chunk"
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))

    aggregate_text = " ".join(chunk.text for chunk in chunks)
    expected_text = " ".join(segment.text for segment in segments)
    assert aggregate_text == expected_text

    assert chunks[0].t_start == pytest.approx(segments[0].start)
    assert chunks[-1].t_end == pytest.approx(segments[-1].end)

    separator = " "
    expected_start_char = 0
    for idx, chunk in enumerate(chunks):
        assert chunk.start_char == expected_start_char
        assert chunk.end_char - chunk.start_char == len(chunk.text)
        assert chunk.t_start is not None and chunk.t_end is not None
        # Update expected_start_char for next chunk
        expected_start_char += len(chunk.text)
        if idx < len(chunks) - 1:
            expected_start_char += len(separator)
        assert chunk.t_start <= chunk.t_end
        assert chunk.t_end - chunk.t_start <= 25.0 + 1e-6

        token_count = len(chunk.text.split())
        assert token_count <= 90

        if chunk.speakers is None:
            continue
        assert chunk.speakers == sorted(set(chunk.speakers))

    times = [chunk.t_start for chunk in chunks if chunk.t_start is not None]
    assert times == sorted(times)
