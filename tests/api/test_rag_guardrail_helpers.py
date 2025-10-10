from types import SimpleNamespace

from theo.services.api.app.ai.rag.guardrail_helpers import derive_snippet, format_anchor


def test_format_anchor_prefers_page_numbers() -> None:
    passage = SimpleNamespace(page_no=7, t_start=None, t_end=None)
    assert format_anchor(passage) == "page 7"


def test_derive_snippet_returns_fallback_when_text_missing() -> None:
    result = SimpleNamespace(text="", snippet="", start_char=None, end_char=None)
    fallback = "fallback snippet"
    assert derive_snippet(result, fallback=fallback) == fallback
