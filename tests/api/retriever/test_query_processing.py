from __future__ import annotations

from theo.infrastructure.api.app.retriever import hybrid


def test_tokenise_and_lexical_score():
    tokens = hybrid._tokenise(" Faith and Works ")
    assert tokens == ["faith", "and", "works"]

    score = hybrid._lexical_score("Works of enduring FAITH", tokens)
    assert score == 2.0


def test_snippet_and_highlights_limitations():
    text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor."
    snippet = hybrid._snippet(text, max_length=20)
    assert snippet.endswith("...")
    assert len(snippet) <= 20

    tokens = hybrid._tokenise("lorem tempor")
    highlights = hybrid._build_highlights(text, tokens, window=30, max_highlights=1)
    assert highlights
    present = {
        token
        for highlight in highlights
        for token in tokens
        if token in highlight.lower()
    }
    assert present

    # Ensure duplicates are not returned when the same token appears repeatedly
    repeated = "tempor tempor tempor"
    highlights = hybrid._build_highlights(repeated, ["tempor"], window=60, max_highlights=3)
    assert highlights == ["tempor tempor tempor"]
