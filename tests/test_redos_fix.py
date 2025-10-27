"""Test ReDoS vulnerability fixes for passage parser."""

import pytest
import time

from theo.infrastructure.api.app.ai.passage import (
    PassageResolutionError,
    resolve_passage_reference,
)


def test_passage_length_validation() -> None:
    """Test that overly long passages are rejected to prevent ReDoS."""
    long_passage = "A" * 201  # Exceeds 200 character limit
    with pytest.raises(PassageResolutionError, match="too long"):
        resolve_passage_reference(long_passage)


def test_redos_pattern_performance() -> None:
    """Test that the regex pattern doesn't exhibit catastrophic backtracking."""
    # Malicious input designed to trigger ReDoS with vulnerable pattern
    # Many spaces and word characters without matching the pattern
    malicious_input = "a " * 50 + "1:1"

    start_time = time.time()
    try:
        resolve_passage_reference(malicious_input)
    except PassageResolutionError:
        pass  # Expected to fail parsing, but should be fast

    elapsed = time.time() - start_time

    # Should complete in well under 1 second (defensive threshold: 0.1s)
    assert elapsed < 0.1, f"Regex took {elapsed}s, possible ReDoS vulnerability"


def test_valid_passages_still_work() -> None:
    """Ensure the fix doesn't break legitimate passage references."""
    assert resolve_passage_reference("Mark 16:9–20") == "Mark.16.9-Mark.16.20"
    assert resolve_passage_reference("John 3:16") == "John.3.16"
    assert resolve_passage_reference("Romans 8") == "Rom.8"
    assert resolve_passage_reference("1 John 1:1") == "1John.1.1"
    assert resolve_passage_reference("Gospel of Mark 1:1") == "Mark.1.1"


def test_edge_case_whitespace_handling() -> None:
    """Test that various whitespace patterns are handled correctly."""
    # Normal whitespace should work
    assert resolve_passage_reference("John  3:16") == "John.3.16"

    # Leading/trailing whitespace
    assert resolve_passage_reference("  John 3:16  ") == "John.3.16"

    # Multiple spaces in book name
    assert resolve_passage_reference("1  John  1:1") == "1John.1.1"
