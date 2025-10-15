from __future__ import annotations

from theo.services.api.app.models.base import Passage
from theo.services.api.app.models.search import HybridSearchRequest
from theo.services.api.app.models.verses import VerseMention
from theo.services.api.app.retriever.export import _mentions_to_export_response


def _build_mention(idx: int) -> VerseMention:
    passage = Passage(
        id=f"passage-{idx}",
        document_id=f"doc-{idx}",
        text=f"Passage text {idx}",
        osis_ref="John.3.16",
        meta={"document_title": f"Document {idx}"},
    )
    return VerseMention(passage=passage, context_snippet=f"Snippet {idx}")


def test_mentions_export_with_invalid_cursor_returns_results() -> None:
    mentions = [_build_mention(idx) for idx in range(1, 4)]
    request = HybridSearchRequest(
        query="test",
        osis="John.3.16",
        mode="mentions",
        cursor="missing-cursor",
        limit=2,
    )

    response = _mentions_to_export_response(mentions, request)

    assert [row.passage.id for row in response.results] == ["passage-1", "passage-2"]
    assert response.total_results == len(mentions)
    assert response.next_cursor == "passage-2"
    assert len(response.results) == request.limit


def test_mentions_export_with_valid_cursor_skips_anchor() -> None:
    mentions = [_build_mention(idx) for idx in range(1, 5)]
    request = HybridSearchRequest(
        query="test",
        osis="John.3.16",
        mode="mentions",
        cursor="passage-2",
        limit=2,
    )

    response = _mentions_to_export_response(mentions, request)

    assert [row.passage.id for row in response.results] == ["passage-3", "passage-4"]
    assert response.total_results == 2
    assert response.next_cursor is None
