"""Tests for AI reasoning modules."""

from __future__ import annotations

import pytest

from theo.services.api.app.ai.reasoning.fallacies import (
    FallacyDetector,
    detect_fallacies,
)
from theo.services.api.app.ai.reasoning.chain_of_thought import (
    build_cot_prompt,
    parse_chain_of_thought,
)
from theo.services.api.app.ai.reasoning.insights import InsightDetector
from theo.services.api.app.ai.reasoning.metacognition import (
    Critique,
    MAX_CITATIONS_IN_PROMPT,
    _detect_bias,
    _extract_alternative_interpretations,
    _identify_weak_citations,
    _select_revision_citations,
    critique_reasoning,
    revise_with_critique,
)
from theo.services.api.app.ai.rag.models import RAGCitation


class TestFallacyDetector:
    """Test logical fallacy detection."""

    def test_detects_ad_hominem(self):
        """Should detect ad hominem attacks."""
        text = "The author is biased and therefore wrong about Paul's view on law."
        warnings = detect_fallacies(text)

        assert len(warnings) > 0
        assert any(w.fallacy_type == "ad_hominem" for w in warnings)
        assert warnings[0].severity == "high"

    def test_detects_appeal_to_authority(self):
        """Should detect bare appeals to authority."""
        text = "Famous scholar John Doe says this, therefore it's true."
        warnings = detect_fallacies(text)

        assert any(w.fallacy_type == "appeal_to_authority" for w in warnings)

    def test_detects_circular_reasoning(self):
        """Should detect circular reasoning."""
        text = "The Bible is true because the Bible says so."
        warnings = detect_fallacies(text)

        assert any(w.fallacy_type == "circular_reasoning" for w in warnings)

    def test_detects_proof_texting(self):
        """Should detect proof-texting (rapid-fire citations)."""
        text = "See Gen.1.1, Gen.1.2, Gen.1.3, Gen.1.4, Gen.1.5 for evidence."
        warnings = detect_fallacies(text)

        assert any(w.fallacy_type == "proof_texting" for w in warnings)

    def test_detects_verse_isolation(self):
        """Should detect verse isolation."""
        text = "The verse clearly says that Jesus is God."
        warnings = detect_fallacies(text)

        assert any(w.fallacy_type == "verse_isolation" for w in warnings)

    def test_no_fallacies_in_clean_text(self):
        """Should not flag clean reasoning."""
        text = "Romans 3:23 states all have sinned. Paul's argument builds on Jewish and Gentile guilt."
        warnings = detect_fallacies(text)

        # Should have no high-severity warnings
        high_severity = [w for w in warnings if w.severity == "high"]
        assert len(high_severity) == 0

    def test_provides_suggestions(self):
        """Should provide remediation suggestions."""
        text = "The author is biased, so their argument is wrong."
        warnings = detect_fallacies(text)

        ad_hom = next(w for w in warnings if w.fallacy_type == "ad_hominem")
        assert ad_hom.suggestion is not None
        assert "argument's logic" in ad_hom.suggestion

    def test_deduplicates_repeated_fallacies(self):
        """Repeated instances of the same fallacy should collapse into one warning."""

        text = "The critic is ignorant. The critic is ignorant. The critic is ignorant."
        warnings = detect_fallacies(text)

        ad_hominems = [w for w in warnings if w.fallacy_type == "ad_hominem"]
        assert len(ad_hominems) == 1
        assert "detected 3" in ad_hominems[0].description.lower()

    def test_handles_legitimate_citation_list_without_false_positive(self):
        """Balanced citation lists should not trigger proof-texting or circular reasoning."""

        text = (
            "Since the text teaches love for enemies (Matt 5:44), Christians wrestle with pacifism. "
            "See Matt 5:38-48, Luke 6:27-36, Rom 12:17-21, 1 Pet 3:9, 1 Thess 5:15 for parallel teachings."
        )
        warnings = detect_fallacies(text)

        flagged_types = {warning.fallacy_type for warning in warnings}
        assert "proof_texting" not in flagged_types
        assert "circular_reasoning" not in flagged_types


class TestChainOfThought:
    """Test chain-of-thought prompting."""

    def test_builds_detective_prompt(self):
        """Should build detective mode prompt."""
        citations = [
            RAGCitation(
                index=1,
                osis="Rom.3.23",
                anchor="page 42",
                passage_id="p1",
                document_id="d1",
                document_title="Romans Commentary",
                snippet="All have sinned and fall short",
            )
        ]

        prompt = build_cot_prompt("What is Paul's view of sin?", citations, mode="detective")

        assert "theological detective" in prompt.lower()
        assert "Understand the Question" in prompt
        assert "Survey Evidence" in prompt
        assert "Rom.3.23" in prompt
        assert "<thinking>" in prompt

    def test_builds_critic_prompt(self):
        """Should build critic mode prompt."""
        citations = [
            RAGCitation(
                index=1,
                osis="John.1.1",
                anchor="context",
                passage_id="p1",
                document_id="d1",
                document_title="Gospel of John",
                snippet="In the beginning was the Word",
            )
        ]

        prompt = build_cot_prompt("Was Jesus divine?", citations, mode="critic")

        assert "skeptical peer reviewer" in prompt.lower()
        assert "Question Every Claim" in prompt
        assert "Check Logic" in prompt

    def test_parses_thinking_tags(self):
        """Should parse <thinking> tags from completion."""
        completion = """
<thinking>
1. **Understand:** The question asks about Paul's soteriology.
2. **Identify:** Key concepts are grace, faith, works.
3. **Survey:** Romans 3 emphasizes faith alone.
</thinking>

Paul argues salvation is by grace through faith, not works.

Sources: [1] Rom.3.23 (page 42)
"""

        cot = parse_chain_of_thought(completion)

        assert len(cot.steps) == 3
        assert cot.steps[0].step_type == "understand"
        assert cot.steps[1].step_type == "identify"
        assert cot.steps[2].step_type == "survey"
        assert "grace, faith, works" in cot.steps[1].content

    def test_handles_missing_thinking_tags(self):
        """Should handle completions without thinking tags."""
        completion = "Just a plain answer. Sources: [1] John.1.1 (context)"

        cot = parse_chain_of_thought(completion)

        assert cot.steps == []
        assert cot.raw_thinking == ""


class TestInsightDetector:
    """Test insight detection."""

    def test_detects_explicit_insights(self, session):
        """Should extract <insight> tags."""
        reasoning = """
<thinking>
Analyzing the evidence...
<insight type="synthesis">
Matthew 5:17 and Romans 10:4 create a tension about Torah's fulfillment
that early church grappled with extensively.
</insight>
</thinking>
"""
        detector = InsightDetector(session)
        insights = detector.detect_from_reasoning(reasoning, [])

        assert len(insights) >= 1
        synthesis_insight = next(i for i in insights if i.insight_type == "synthesis")
        assert "Matthew 5:17" in synthesis_insight.description
        assert "Romans 10:4" in synthesis_insight.description

    def test_detects_cross_references(self, session):
        """Should auto-detect cross-references across books."""
        passages = [
            {"id": "p1", "osis_ref": "Gen.1.1"},
            {"id": "p2", "osis_ref": "John.1.1"},
            {"id": "p3", "osis_ref": "Col.1.15"},
            {"id": "p4", "osis_ref": "Heb.1.3"},
        ]

        detector = InsightDetector(session)
        insights = detector.detect_from_reasoning("", passages)

        cross_ref = next((i for i in insights if i.insight_type == "cross_ref"), None)
        assert cross_ref is not None
        assert len(cross_ref.supporting_passages) == 4

    def test_detects_patterns(self, session):
        """Should detect frequently cited verses."""
        # Same verse in 5 different documents
        passages = [
            {"id": f"p{i}", "osis_ref": "John.1.1", "document_id": f"d{i}"}
            for i in range(6)
        ]

        detector = InsightDetector(session)
        insights = detector.detect_from_reasoning("", passages)

        pattern = next((i for i in insights if i.insight_type == "pattern"), None)
        assert pattern is not None
        assert "John.1.1" in pattern.description
        assert "anchor point" in pattern.description


class TestMetacognition:
    """Test meta-cognitive critique."""

    def test_critiques_fallacious_reasoning(self):
        """Should detect fallacies and lower quality score."""
        reasoning = "The author is biased, so this argument is wrong."
        answer = "Therefore Paul didn't really mean what he said."
        citations = []

        critique = critique_reasoning(reasoning, answer, citations)

        assert critique.reasoning_quality < 70  # Should be penalized
        assert len(critique.fallacies_found) > 0
        assert len(critique.recommendations) > 0

    def test_identifies_weak_citations(self):
        """Should flag citations without explanation."""
        reasoning = "Paul teaches grace."
        answer = "See [1] for proof."
        citations = [
            {
                "index": 1,
                "passage_id": "p1",
                "snippet": "For by grace you have been saved through faith",
            }
        ]

        critique = critique_reasoning(reasoning, answer, citations)

        assert len(critique.weak_citations) > 0

    def test_detects_perspective_bias(self):
        """Should detect apologetic or skeptical bias."""
        reasoning = "Everything is coherent and harmonious and consistent and resolves perfectly."
        answer = "No contradictions exist."
        citations = []

        critique = critique_reasoning(reasoning, answer, citations)

        assert len(critique.bias_warnings) > 0
        assert any("apologetic" in w for w in critique.bias_warnings)

    def test_accepts_high_quality_reasoning(self):
        """Should rate clean reasoning highly."""
        reasoning = """
<thinking>
1. Romans 3:23 states universal sinfulness
2. This builds on Jewish concept from Psalms
3. Paul's argument is coherent within his framework
4. Alternative readings exist but this is standard interpretation
</thinking>
"""
        answer = "Paul teaches all have sinned [1]. This echoes Psalm 14 [2]."
        citations = [
            {"index": 1, "passage_id": "p1", "snippet": "all have sinned"},
            {"index": 2, "passage_id": "p2", "snippet": "there is no one righteous"},
        ]

        critique = critique_reasoning(reasoning, answer, citations)

        assert critique.reasoning_quality >= 65
        assert len(critique.fallacies_found) == 0


class TestMetacognitionHeuristics:
    """Test targeted metacognition helper behaviours."""

    def test_identify_weak_citations_requires_context_overlap(self):
        """A citation without proximate explanation should be flagged as weak."""

        citations = [
            {
                "index": 1,
                "passage_id": "p1",
                "snippet": "For by grace you have been saved through faith",
                "osis": "Eph.2.8",
            }
        ]
        answer = "Paul emphasises grace [1] but offers no further detail."

        weak = _identify_weak_citations(answer, citations)

        assert weak == ["p1"]

    def test_identify_weak_citations_skips_invalid_entries(self):
        """Malformed citations should be ignored without crashing."""

        citations = [
            {"index": 0, "snippet": ""},
            {"index": 2, "passage_id": "p2", "snippet": None},
            {
                "index": 3,
                "passage_id": "p3",
                "snippet": "Love your enemies",
                "osis": "Matt.5.44",
            },
        ]
        answer = "Jesus commands love for enemies [3]."

        weak = _identify_weak_citations(answer, citations)

        assert weak == []

    def test_bias_detection_respects_negations(self):
        """Negated bias markers should not raise warnings."""

        trace = "The commentators note a lack of harmony and question simplistic readings."
        answer = "It is not harmonious, and the inconsistency must be addressed."

        warnings = _detect_bias(trace, answer)

        assert warnings == []

    def test_bias_detection_flags_monolithic_language(self):
        """Strongly one-sided language should still raise a warning."""

        trace = "The argument is harmonious and consistent."
        answer = "It seamlessly resolves every tension."

        warnings = _detect_bias(trace, answer)

        assert any("apologetic" in warning for warning in warnings)

    def test_extract_alternative_interpretations_detects_common_markers(self):
        """The extractor should pick up inline alternatives from common phrasing."""

        reasoning = (
            "- Alternative interpretation: that the covenant refers to oral law.\n"
            "Some scholars interpret the works of the law as ethnic boundary markers, while others see it as moral effort.\n"
            "Critics argue it signals hypocrisy, but others contend it's rhetorical."
        )
        answer = (
            "Alternatively, it could highlight covenant membership. "
            "Another interpretation is that it emphasises humility in practice."
        )

        interpretations = _extract_alternative_interpretations(reasoning, answer)

        assert "the covenant refers to oral law" in interpretations
        assert "the works of the law as ethnic boundary markers" in interpretations
        assert "highlight covenant membership" in interpretations
        assert "signals hypocrisy" in interpretations
        assert any("rhetorical" in item for item in interpretations)

    def test_extract_alternative_interpretations_deduplicates_clauses(self):
        """Repeated alternative phrasings should collapse into one entry."""

        reasoning = (
            "Some scholars interpret the promise as symbolic fulfillment.\n"
            "Alternatively, it might point to covenant loyalty.\n"
            "Some scholars interpret the promise as symbolic fulfillment."
        )
        interpretations = _extract_alternative_interpretations(reasoning, "")

        assert interpretations.count("the promise as symbolic fulfillment") == 1
        assert "point to covenant loyalty" in interpretations

    def test_revision_prompt_prioritises_referenced_and_weak_citations(self):
        """Selected citations should include weak and referenced indices within limit."""

        citations = [
            {
                "index": idx,
                "passage_id": f"p{idx}",
                "snippet": f"Snippet text {idx} with context",
                "osis": f"Book.{idx}",
                "anchor": "context",
            }
            for idx in range(1, MAX_CITATIONS_IN_PROMPT + 5)
        ]
        critique = Critique(
            reasoning_quality=55,
            fallacies_found=[],
            weak_citations=["p1", "p2"],
            alternative_interpretations=[],
            bias_warnings=[],
            recommendations=[],
        )
        answer = "The discussion references [1], [2], and [3] explicitly."

        selected = _select_revision_citations(answer, critique, citations)

        assert len(selected) <= MAX_CITATIONS_IN_PROMPT
        selected_indices = [citation["index"] for citation in selected]
        assert {1, 2}.issubset(selected_indices)
        assert 3 in selected_indices


class DummyRevisionClient:
    """Simple stand-in for the language model client during tests."""

    def __init__(self, completion: str) -> None:
        self._completion = completion
        self.calls = 0
        self.last_prompt: str | None = None

    def generate(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float = 0.2,
        max_output_tokens: int = 800,
        cache_key: str | None = None,
    ) -> str:
        self.calls += 1
        self.last_prompt = prompt
        return self._completion


class TestRevision:
    """Tests for critique-driven revision."""

    def test_revise_with_critique_resolves_fallacy(self):
        """LLM revision should address detected fallacies."""

        original_answer = (
            "Skeptics are ignorant, so their objections fail; Paul plainly proves the point. "
            "Sources: [1]"
        )
        citations = [
            {
                "index": 1,
                "snippet": "Romans 3:23 emphasises that all people depend on grace.",
                "passage_id": "p1",
                "osis": "Rom.3.23",
                "anchor": "context",
            }
        ]

        critique = critique_reasoning(original_answer, original_answer, citations)
        assert any(f.fallacy_type == "ad_hominem" for f in critique.fallacies_found)

        client = DummyRevisionClient(
            """
<revised_answer>Paul's argument should focus on the shared need for grace that Romans 3:23 highlights, addressing objections with evidence rather than personal attacks. Sources: [1]</revised_answer>
            """.strip()
        )

        result = revise_with_critique(
            original_answer=original_answer,
            critique=critique,
            client=client,
            model="test-model",
            reasoning_trace=original_answer,
            citations=citations,
        )

        assert result.revised_answer != original_answer
        assert any("Resolved fallacy" in item for item in result.critique_addressed)
        assert result.quality_delta >= 0
        assert result.revised_critique.reasoning_quality >= critique.reasoning_quality
        assert client.calls == 1
        assert client.last_prompt is not None and "ad_hominem" in client.last_prompt

    def test_revise_with_critique_handles_plain_completion(self):
        """Revision should handle completions without XML tags."""

        original_answer = (
            "The passage clearly proves the doctrine without nuance or counterpoint. Sources: [1]"
        )
        citations = [
            {
                "index": 1,
                "snippet": "The text calls the community to humility and repentance.",
                "passage_id": "p2",
                "osis": "Mic.6.8",
                "anchor": "context",
            }
        ]

        critique = critique_reasoning(original_answer, original_answer, citations)
        assert critique.bias_warnings, "Expected overconfidence bias to be flagged"

        client = DummyRevisionClient(
            "The passage invites humility and justice, reminding readers to walk with God in grace. Sources: [1]"
        )

        result = revise_with_critique(
            original_answer=original_answer,
            critique=critique,
            client=client,
            model="test-model",
            reasoning_trace=original_answer,
            citations=citations,
        )

        assert result.revised_answer.startswith("The passage invites humility")
        assert "Mitigated bias" in " ".join(result.critique_addressed)
        assert result.improvements
        assert result.revised_critique.reasoning_quality >= critique.reasoning_quality


@pytest.fixture
def session():
    """Mock session for testing."""
    # In real tests, would use actual DB session
    class MockSession:
        pass

    return MockSession()
