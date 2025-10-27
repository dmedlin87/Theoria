from theo.infrastructure.api.app.ai.rag.revisions import (
    critique_to_schema,
    revision_to_schema,
    should_attempt_revision,
)
from theo.infrastructure.api.app.ai.reasoning.fallacies import FallacyWarning
from theo.infrastructure.api.app.ai.reasoning.metacognition import Critique, RevisionResult


def test_should_attempt_revision_triggers_on_fallacies() -> None:
    critique = Critique(
        reasoning_quality=95,
        fallacies_found=[
            FallacyWarning(
                fallacy_type="ad_hominem",
                severity="high",
                description="Attacks the speaker",
                matched_text="The critic is ignorant",
            )
        ],
    )

    assert should_attempt_revision(critique) is True


def test_should_attempt_revision_respects_only_acceptable_feedback() -> None:
    critique = Critique(
        reasoning_quality=90,
        recommendations=["Response is acceptable as is."],
    )

    assert should_attempt_revision(critique) is False


def test_critique_to_schema_transforms_dataclass_fields() -> None:
    critique = Critique(
        reasoning_quality=70,
        fallacies_found=[
            FallacyWarning(
                fallacy_type="straw_man",
                severity="medium",
                description="Misrepresents opposing view",
                matched_text="Skeptics think scripture is useless",
                suggestion="Engage with the actual argument",
            )
        ],
        weak_citations=["passage-1"],
        alternative_interpretations=["Consider the broader literary context"],
        bias_warnings=["leans heavily on modernism"],
        recommendations=["Clarify the counterargument"],
    )

    schema = critique_to_schema(critique)

    assert schema.reasoning_quality == 70
    assert schema.fallacies_found[0].fallacy_type == "straw_man"
    assert schema.fallacies_found[0].suggestion == "Engage with the actual argument"
    assert schema.weak_citations == ["passage-1"]
    assert schema.alternative_interpretations == [
        "Consider the broader literary context"
    ]
    assert schema.bias_warnings == ["leans heavily on modernism"]
    assert schema.recommendations == ["Clarify the counterargument"]


def test_revision_to_schema_includes_nested_critique() -> None:
    nested_critique = Critique(
        reasoning_quality=60,
        recommendations=["Needs clearer citation handling"],
    )
    revision = RevisionResult(
        original_answer="Initial answer",
        revised_answer="Improved answer",
        critique_addressed=["weak citations"],
        improvements="Added stronger citations",
        quality_delta=10,
        revised_critique=nested_critique,
    )

    schema = revision_to_schema(revision)

    assert schema.original_answer == "Initial answer"
    assert schema.revised_answer == "Improved answer"
    assert schema.critique_addressed == ["weak citations"]
    assert schema.improvements == "Added stronger citations"
    assert schema.quality_delta == 10
    assert schema.revised_critique.reasoning_quality == 60
    assert schema.revised_critique.recommendations == [
        "Needs clearer citation handling"
    ]
