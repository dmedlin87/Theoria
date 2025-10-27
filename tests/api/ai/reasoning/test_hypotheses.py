"""Unit tests for hypothesis generation and testing utilities."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from theo.infrastructure.api.app.ai.reasoning import hypotheses as hypotheses_module
from theo.infrastructure.api.app.ai.reasoning.hypotheses import (
    Hypothesis,
    HypothesisGenerator,
    test_hypothesis as run_hypothesis_test,
)
from theo.infrastructure.api.app.models.search import HybridSearchResult


class TestHypothesisExtraction:
    """Pattern-based extraction from reasoning traces."""

    def test_extracts_multiple_candidates(self):
        """Should pull out implicit hypotheses from narrative reasoning."""

        session = MagicMock()
        generator = HypothesisGenerator(session)
        reasoning = (
            "The study surfaces competing readings. "
            "One possibility is that Jesus used parables to reveal the kingdom to insiders [1]. "
            "Alternatively, the parables might primarily expose the hardness of the crowds [2], which seems unlikely. "
            "Another hypothesis is that the parables fulfil Isaiah's warning about dull hearing [3]."
        )

        extracted = generator.extract_from_reasoning(reasoning)

        assert len(extracted) >= 2
        claims = {hyp.claim for hyp in extracted}
        assert any("used parables" in claim for claim in claims)
        assert any("hardness of the crowds" in claim for claim in claims)
        confidences = [hyp.confidence for hyp in extracted]
        assert max(confidences) <= 1.0 and min(confidences) >= 0.2
        support_counts = [len(hyp.supporting_passages) for hyp in extracted]
        assert any(count >= 1 for count in support_counts)


class TestHypothesisTesting:
    """Integration of hypothesis testing with retrieval heuristics."""

    def test_updates_confidence_and_tracks_evidence(self, monkeypatch):
        """Should classify retrieval results and update hypothesis state."""

        session = MagicMock()
        hypothesis = Hypothesis(
            id="h1",
            claim="Jesus uses parables to reveal the kingdom to insiders",
            confidence=0.4,
        )

        supportive_result = HybridSearchResult(
            id="p1",
            document_id="d1",
            text="This passage affirms the disciples are given understanding of the mysteries.",
            osis_ref="Matt.13.11",
            score=0.92,
            meta=None,
            snippet="The text affirms disciples receive the mysteries of the kingdom, supporting insider revelation.",
            rank=1,
        )
        contradictory_result = HybridSearchResult(
            id="p2",
            document_id="d2",
            text="However, the narrative notes the crowds were not granted insight into the parables.",
            osis_ref="Mark.4.11",
            score=0.81,
            meta=None,
            snippet="However, the crowds were not granted insight, challenging the universal insider claim.",
            rank=2,
        )

        def fake_search(self, *, query, osis, filters, k):  # noqa: D401 - signature enforced by monkeypatch
            assert query == hypothesis.claim
            assert osis is None
            assert k == 3
            return [supportive_result, contradictory_result]

        monkeypatch.setattr(hypotheses_module.PassageRetriever, "search", fake_search)

        assert (
            hypotheses_module._classify_passage_evidence(
                hypothesis.claim, contradictory_result.snippet
            )
            == "contradiction"
        )

        outcome = run_hypothesis_test(hypothesis, session, retrieval_budget=3)

        assert outcome.new_passages_found == 2
        assert outcome.supporting_added == 1
        assert outcome.contradicting_added == 1
        assert pytest.approx(outcome.updated_confidence, rel=1e-3) == hypothesis.confidence
        assert pytest.approx(outcome.confidence_delta, rel=1e-3) == (
            outcome.updated_confidence - 0.4
        )
        assert outcome.recommendation == "gather_more"
        assert hypothesis.last_test is outcome
        assert len(hypothesis.supporting_passages) == 1
        assert len(hypothesis.contradicting_passages) == 1
        assert "crowds" in hypothesis.contradicting_passages[0].snippet.lower()
