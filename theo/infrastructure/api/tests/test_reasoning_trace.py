from theo.infrastructure.api.app.ai.rag.reasoning_trace import (
    build_reasoning_trace_from_completion,
)


def test_build_reasoning_trace_from_completion_parses_steps():
    completion = """<thinking>
1. **Understand the Question:** Reframed John 1:1 in context of Genesis.[1]
2. **Synthesize:** Linked the Logos to creation themes and divine identity.[1][2]
</thinking>

The Word present at creation affirms Jesus' divinity.

Sources: [1] John.1.1 (John 1:1); [2] Gen.1.1 (Genesis 1:1)
"""

    trace = build_reasoning_trace_from_completion(completion, mode="detective")

    assert trace is not None
    assert trace.strategy == "Detective reasoning"
    assert len(trace.steps) == 2
    assert trace.steps[0].label == "Understand the question"
    assert trace.steps[0].citations == [0]
    assert trace.steps[1].citations == [0, 1]
    assert trace.summary.startswith("Reframed John 1:1")


def test_build_reasoning_trace_returns_none_without_thinking_section():
    completion = "The answer without reasoning tags."

    assert build_reasoning_trace_from_completion(completion) is None
    assert build_reasoning_trace_from_completion(None) is None
