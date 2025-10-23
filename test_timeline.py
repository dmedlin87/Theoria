"""Quick test script for CS-001 Reasoning Timeline."""

from datetime import UTC, datetime

from theo.services.api.app.models.reasoning import (
    ReasoningStep,
    ReasoningStepStatus,
    ReasoningStepType,
    ReasoningTimeline,
)


def test_reasoning_timeline():
    """Test that we can create and serialize a reasoning timeline."""
    now = datetime.now(UTC)

    # Create a sample timeline
    timeline = ReasoningTimeline(
        session_id="test-123",
        question="What is justification by faith?",
        steps=[
            ReasoningStep(
                id="test-123-understand",
                step_type=ReasoningStepType.UNDERSTAND,
                status=ReasoningStepStatus.COMPLETED,
                title="Understanding the question",
                description="Analyzing theological context",
                started_at=now.isoformat(),
                completed_at=now.isoformat(),
                duration_ms=450,
            ),
            ReasoningStep(
                id="test-123-gather",
                step_type=ReasoningStepType.GATHER,
                status=ReasoningStepStatus.COMPLETED,
                title="Gathering evidence",
                description="Retrieved passages and commentaries",
                citations=["Romans 3:28", "Galatians 2:16", "Ephesians 2:8-9"],
                tools_called=["hybrid_search", "semantic_retrieval"],
                started_at=now.isoformat(),
                completed_at=now.isoformat(),
                duration_ms=1200,
            ),
            ReasoningStep(
                id="test-123-synthesize",
                step_type=ReasoningStepType.SYNTHESIZE,
                status=ReasoningStepStatus.COMPLETED,
                title="Final synthesis",
                description="Integrating perspectives",
                output_summary="Comprehensive answer complete",
                started_at=now.isoformat(),
                completed_at=now.isoformat(),
                duration_ms=300,
            ),
        ],
        current_step_index=2,
        total_duration_ms=1950,
        status="completed",
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )

    # Test serialization
    timeline_dict = timeline.model_dump()

    print("✅ Timeline Model Created Successfully")
    print(f"   Session: {timeline.session_id}")
    print(f"   Question: {timeline.question}")
    print(f"   Steps: {len(timeline.steps)}")
    print(f"   Status: {timeline.status}")
    print(f"   Total Duration: {timeline.total_duration_ms}ms")
    print()

    # Print each step
    print("📋 Timeline Steps:")
    for i, step in enumerate(timeline.steps, 1):
        print(f"   {i}. {step.title} ({step.step_type})")
        print(f"      Status: {step.status}")
        print(f"      Duration: {step.duration_ms}ms")
        if step.citations:
            print(f"      Citations: {', '.join(step.citations)}")
        if step.tools_called:
            print(f"      Tools: {', '.join(step.tools_called)}")
        print()

    # Test JSON serialization
    import json
    timeline_json = json.dumps(timeline_dict, indent=2, default=str)
    print("✅ JSON Serialization Works")
    print(f"   Size: {len(timeline_json)} bytes")
    print()

    # Verify structure
    assert timeline_dict["session_id"] == "test-123"
    assert len(timeline_dict["steps"]) == 3
    assert timeline_dict["steps"][0]["step_type"] == "understand"
    assert timeline_dict["steps"][1]["citations"] == ["Romans 3:28", "Galatians 2:16", "Ephesians 2:8-9"]

    print("✅ All Assertions Passed!")
    print()
    print("🎯 Timeline model is working correctly!")

    return timeline

if __name__ == "__main__":
    test_reasoning_timeline()
