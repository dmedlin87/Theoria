> **Archived on October 26, 2025** - Development test file for CS-001 timeline integration, preserved for reference.

"""Test CS-001 Reasoning Timeline integration with chat."""

import json

from theo.services.api.app.ai.rag import RAGAnswer, RAGCitation, ReasoningTrace
from theo.services.api.app.routes.ai.workflows.chat import (
    _create_mock_reasoning_timeline,
)


def test_timeline_integration():
    """Test that timeline integrates with existing RAGAnswer."""

    # Create mock RAGAnswer with citations
    answer = RAGAnswer(
        summary="Justification by faith is a key doctrine in Christian theology.",
        citations=[
            RAGCitation(
                index=0,
                osis="Rom.3.28",
                anchor="Romans 3:28",
                snippet="For we hold that one is justified by faith apart from works of the law.",
            ),
            RAGCitation(
                index=1,
                osis="Gal.2.16",
                anchor="Galatians 2:16",
                snippet="Yet we know that a person is not justified by works of the law but through faith in Jesus Christ.",
            ),
        ],
        model_name="gpt-4",
    )

    print("✅ Created mock RAGAnswer")
    print(f"   Summary: {answer.summary[:50]}...")
    print(f"   Citations: {len(answer.citations)}")
    print()

    # Test timeline creation
    session_id = "test-session-123"
    question = "What is justification by faith?"

    _create_mock_reasoning_timeline(session_id, question, answer)

    print("✅ Timeline attached to answer")
    print()

    # Verify reasoning_trace was populated
    assert answer.reasoning_trace is not None, "reasoning_trace should not be None"
    assert isinstance(answer.reasoning_trace, ReasoningTrace), "Should be ReasoningTrace instance"
    assert len(answer.reasoning_trace.steps) == 7, "Should have 7 steps"

    print("✅ Reasoning trace validation passed")
    print(f"   Steps: {len(answer.reasoning_trace.steps)}")
    print(f"   Summary: {answer.reasoning_trace.summary}")
    print(f"   Strategy: {answer.reasoning_trace.strategy}")
    print()

    # Print steps
    print("📋 Timeline Steps:")
    for i, step in enumerate(answer.reasoning_trace.steps, 1):
        print(f"   {i}. {step.label}")
        print(f"      Status: {step.status}")
        if step.detail:
            print(f"      Detail: {step.detail}")
        if step.citations:
            print(f"      Citations: {step.citations}")
        if step.outcome:
            print(f"      Outcome: {step.outcome}")
        print()

    # Test serialization
    answer_dict = answer.model_dump()
    assert "reasoning_trace" in answer_dict, "reasoning_trace should be in serialized output"
    assert answer_dict["reasoning_trace"] is not None, "reasoning_trace should not be null"

    print("✅ Serialization works")
    print(f"   Reasoning trace keys: {list(answer_dict['reasoning_trace'].keys())}")
    print()

    # Test JSON serialization
    answer_json = json.dumps(answer_dict, indent=2, default=str)
    print("✅ JSON serialization successful")
    print(f"   Size: {len(answer_json)} bytes")
    print()

    print("🎯 Timeline integration test PASSED!")
    print()
    print("Next steps:")
    print("  1. Start API server: uvicorn theo.services.api.app.main:app --reload")
    print("  2. Send chat request to /chat endpoint")
    print("  3. Verify reasoning_trace in response")
    print("  4. Frontend will automatically display it using existing ReasoningTrace component")

    return answer

if __name__ == "__main__":
    test_timeline_integration()
