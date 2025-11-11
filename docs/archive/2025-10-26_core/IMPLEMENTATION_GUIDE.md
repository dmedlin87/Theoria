> **Archived on 2025-10-26**

# AI Agent Thinking Enhancement - Implementation Guide

## Quick Start

### What We Built

A comprehensive reasoning framework that transforms the Theoria agent from a reactive RAG system into an autonomous theological detective with:

✅ **Logical fallacy detection** - 9 fallacy types with suggestions  
✅ **Chain-of-thought scaffolding** - 4 reasoning modes (detective, critic, apologist, synthesizer)  
✅ **Hypothesis generation** - Form and test competing theories  
✅ **Insight detection** - Auto-discover novel connections  
✅ **Meta-cognitive critique** - Self-assess reasoning quality  
✅ **Multi-perspective synthesis** - Compare skeptical/apologetic/neutral views  

### File Structure

```
theo/infrastructure/api/app/ai/reasoning/
├── __init__.py                    # Module exports
├── fallacies.py                   # Logical fallacy detector
├── chain_of_thought.py            # CoT prompting & parsing
├── hypotheses.py                  # Hypothesis generation & testing
├── insights.py                    # Insight detection
├── metacognition.py               # Self-critique & revision
└── perspectives.py                # Multi-perspective synthesis

tests/api/ai/
└── test_reasoning_modules.py      # Comprehensive tests

docs/
├── AGENT_THINKING_ENHANCEMENT.md  # Full design doc
├── IMPLEMENTATION_GUIDE.md         # This file
└── migrations/
    └── add_reasoning_tables.sql    # Database schema
```

---

## Phase 1: Foundation (Immediate)

### Step 1: Run Database Migration

```bash
# Apply reasoning tables schema
psql $DATABASE_URL < docs/migrations/add_reasoning_tables.sql

# Verify tables created
psql $DATABASE_URL -c "\dt reasoning*"
```

### Step 2: Run Tests

```bash
# Install if needed
pip install pytest pytest-cov

# Run reasoning module tests
pytest tests/api/ai/test_reasoning_modules.py -v

# Check coverage
pytest tests/api/ai/test_reasoning_modules.py --cov=theo.services.api.app.ai.reasoning --cov-report=html
```

### Step 3: Test Fallacy Detection

```python
from theo.services.api.app.ai.reasoning.fallacies import detect_fallacies

# Example 1: Ad hominem
text = "Ehrman is biased, so his argument about Jesus's divinity is wrong."
warnings = detect_fallacies(text)
print(f"Found {len(warnings)} fallacies")
print(warnings[0].suggestion)

# Example 2: Proof-texting
text = "See Gen.1.1, Gen.1.2, Gen.1.3, Gen.1.4, Gen.1.5, Gen.1.6 for evidence."
warnings = detect_fallacies(text)
print(warnings[0].fallacy_type)  # "proof_texting"

# Example 3: Clean reasoning (should pass)
text = "Romans 3:23 states all have sinned. Paul builds this argument from Psalm 14."
warnings = detect_fallacies(text)
high_severity = [w for w in warnings if w.severity == "high"]
assert len(high_severity) == 0
```

### Step 4: Test Chain-of-Thought Prompting

```python
from theo.services.api.app.ai.reasoning.chain_of_thought import build_cot_prompt
from theo.services.api.app.ai.rag.models import RAGCitation

# Create citations
citations = [
    RAGCitation(
        index=1,
        osis="Rom.3.23",
        anchor="page 42",
        passage_id="p1",
        document_id="d1",
        document_title="Romans Commentary",
        snippet="All have sinned and fall short of God's glory"
    ),
    RAGCitation(
        index=2,
        osis="Rom.5.8",
        anchor="page 58",
        passage_id="p2",
        document_id="d1",
        document_title="Romans Commentary",
        snippet="While we were still sinners, Christ died for us"
    )
]

# Build detective mode prompt
prompt = build_cot_prompt(
    question="What is Paul's view of human sinfulness in Romans?",
    citations=citations,
    mode="detective"
)

print(prompt)
# Will include structured steps: Understand → Identify → Survey → Detect → Weigh → Check → Synthesize
```

### Step 5: Integrate into Existing Workflow

**Minimal integration** - Add fallacy detection to existing RAG pipeline:

```python
# In theo/infrastructure/api/app/ai/rag/workflow.py

from ..reasoning.fallacies import detect_fallacies

class GuardedAnswerPipeline:
    def compose(self, *, question, results, ...):
        # ... existing code ...
        
        # After validation, before return:
        from ..reasoning.fallacies import detect_fallacies
        fallacy_warnings = detect_fallacies(model_output)
        
        # Add to answer metadata
        answer.metadata = answer.metadata or {}
        answer.metadata['fallacy_warnings'] = [
            {
                'type': w.fallacy_type,
                'severity': w.severity,
                'description': w.description,
                'suggestion': w.suggestion
            }
            for w in fallacy_warnings
        ]
        
        return answer
```

---

## Phase 2: Chain-of-Thought Integration (Week 2)

### Extend Workflow with CoT

Create `theo/infrastructure/api/app/ai/rag/workflow_enhanced.py`:

```python
from ..reasoning.chain_of_thought import build_cot_prompt, parse_chain_of_thought
from ..reasoning.fallacies import detect_fallacies
from ..reasoning.metacognition import critique_reasoning

class ReasoningPipeline(GuardedAnswerPipeline):
    """Enhanced pipeline with chain-of-thought reasoning."""
    
    def compose_with_reasoning(
        self,
        question: str,
        results: list,
        mode: str = "detective",
        enable_critique: bool = True,
    ):
        # 1. Build CoT prompt instead of basic prompt
        citations = build_citations(results)
        
        # Optionally enrich with contradictions
        osis_refs = extract_osis_from_question(question)
        if osis_refs:
            from ...research.contradictions import search_contradictions
            contradictions = search_contradictions(
                self.session,
                osis=osis_refs,
                limit=5
            )
        else:
            contradictions = None
        
        prompt = build_cot_prompt(
            question=question,
            citations=citations,
            mode=mode,
            contradictions=[c.model_dump() for c in contradictions] if contradictions else None
        )
        
        # 2. Generate with LLM
        completion = self._generate(prompt)  # Your existing generation logic
        
        # 3. Parse reasoning trace
        chain_of_thought = parse_chain_of_thought(completion)
        
        # 4. Detect fallacies
        fallacy_warnings = detect_fallacies(completion)
        
        # 5. Self-critique (if enabled)
        critique = None
        if enable_critique:
            critique = critique_reasoning(
                reasoning_trace=chain_of_thought.raw_thinking,
                answer=completion,
                citations=[c.model_dump() for c in citations]
            )
        
        # 6. Return enhanced answer
        return {
            'answer': completion,
            'chain_of_thought': {
                'steps': [
                    {
                        'step_number': s.step_number,
                        'step_type': s.step_type,
                        'content': s.content
                    }
                    for s in chain_of_thought.steps
                ],
                'raw_thinking': chain_of_thought.raw_thinking
            },
            'fallacy_warnings': [
                {
                    'type': w.fallacy_type,
                    'severity': w.severity,
                    'matched_text': w.matched_text,
                    'suggestion': w.suggestion
                }
                for w in fallacy_warnings
            ],
            'critique': {
                'quality': critique.reasoning_quality,
                'recommendations': critique.recommendations,
                'bias_warnings': critique.bias_warnings
            } if critique else None,
            'citations': [c.model_dump() for c in citations]
        }
```

### Add API Endpoint

In `theo/infrastructure/api/app/ai/router.py`:

```python
@router.post("/chat/enhanced", response_model=EnhancedReasoningResponse)
async def enhanced_chat(
    request: EnhancedChatRequest,
    session: Session = Depends(get_session),
):
    """Enhanced chat with chain-of-thought reasoning."""
    
    pipeline = ReasoningPipeline(session, get_llm_registry(session))
    
    # Retrieve passages
    from ..search.hybrid import search_passages
    results = search_passages(
        session,
        query=request.question,
        osis=request.osis,
        filters=request.filters
    )
    
    # Generate with reasoning
    response = pipeline.compose_with_reasoning(
        question=request.question,
        results=results,
        mode=request.mode or "detective",
        enable_critique=request.enable_critique
    )
    
    return response
```

### UI Integration

In `theo/services/web/app/components/ReasoningTrace.tsx`:

```typescript
interface ReasoningTraceProps {
  steps: ReasoningStep[];
  fallacyWarnings: FallacyWarning[];
  critique?: Critique;
}

export function ReasoningTrace({ steps, fallacyWarnings, critique }: ReasoningTraceProps) {
  return (
    <div className="reasoning-trace">
      <h3>Reasoning Steps</h3>
      
      {steps.map((step) => (
        <div key={step.step_number} className={`step step-${step.step_type}`}>
          <div className="step-header">
            {step.step_number}. {step.step_type.toUpperCase()}
          </div>
          <div className="step-content">
            {step.content}
          </div>
        </div>
      ))}
      
      {fallacyWarnings.length > 0 && (
        <div className="fallacy-warnings">
          <h4>⚠️ Logical Issues Detected</h4>
          {fallacyWarnings.map((warning, idx) => (
            <div key={idx} className={`warning warning-${warning.severity}`}>
              <strong>{warning.type}:</strong> {warning.description}
              {warning.suggestion && <p className="suggestion">{warning.suggestion}</p>}
            </div>
          ))}
        </div>
      )}
      
      {critique && (
        <div className="critique">
          <h4>Self-Critique</h4>
          <div className="quality-score">
            Quality: {critique.quality}/100
          </div>
          {critique.recommendations.map((rec, idx) => (
            <li key={idx}>{rec}</li>
          ))}
        </div>
      )}
    </div>
  );
}
```

---

## Phase 3: Autonomous Exploration (Week 3-4)

### Implement Explorer Loop

Create `theo/infrastructure/api/app/ai/agents/explorer.py`:

```python
from ..reasoning.hypotheses import HypothesisGenerator, test_hypothesis
from ..reasoning.insights import detect_insights
from ...search.hybrid import search_passages

class AutonomousExplorer:
    """Agent that autonomously explores theological questions."""
    
    def __init__(self, session, registry, max_iterations=5, retrieval_budget=50):
        self.session = session
        self.registry = registry
        self.max_iterations = max_iterations
        self.retrieval_budget = retrieval_budget
        self.passages_retrieved = 0
    
    def explore(self, question: str, initial_results: list):
        """Autonomously explore a question through iterative retrieval."""
        
        # 1. Generate initial hypotheses
        hypothesis_gen = HypothesisGenerator(self.session)
        hypotheses = hypothesis_gen.generate_from_question(
            question,
            [r.model_dump() for r in initial_results]
        )
        
        exploration_log = []
        
        for iteration in range(self.max_iterations):
            # 2. Identify knowledge gaps
            gaps = self._detect_knowledge_gaps(hypotheses, question)
            
            if not gaps or self.passages_retrieved >= self.retrieval_budget:
                break
            
            # 3. Generate follow-up queries
            follow_up_queries = self._generate_follow_ups(gaps)
            
            # 4. Retrieve new evidence
            new_results = []
            for query in follow_up_queries[:3]:  # Max 3 per iteration
                results = search_passages(self.session, query=query, limit=5)
                new_results.extend(results)
                self.passages_retrieved += len(results)
            
            # 5. Update hypotheses
            for hyp in hypotheses:
                test_result = test_hypothesis(hyp, self.session)
                hyp.confidence = test_result.updated_confidence
            
            exploration_log.append({
                'iteration': iteration + 1,
                'gaps_identified': gaps,
                'queries_generated': follow_up_queries,
                'passages_found': len(new_results),
                'hypothesis_updates': [
                    {'claim': h.claim, 'confidence': h.confidence}
                    for h in hypotheses
                ]
            })
            
            # 6. Check convergence
            if self._has_converged(hypotheses):
                break
        
        return {
            'hypotheses': hypotheses,
            'iterations': len(exploration_log),
            'total_passages': self.passages_retrieved,
            'log': exploration_log
        }
    
    def _detect_knowledge_gaps(self, hypotheses, question):
        """Identify what's missing to test hypotheses."""
        gaps = []
        
        # Check for missing perspectives
        perspectives_present = set()
        for hyp in hypotheses:
            perspectives_present.update(hyp.perspective_scores.keys())
        
        if 'skeptical' not in perspectives_present:
            gaps.append("Missing skeptical perspective")
        if 'apologetic' not in perspectives_present:
            gaps.append("Missing apologetic perspective")
        
        # Check for low-confidence hypotheses needing more evidence
        for hyp in hypotheses:
            if hyp.confidence < 0.6:
                gaps.append(f"Low confidence on: {hyp.claim[:50]}...")
        
        return gaps
    
    def _generate_follow_ups(self, gaps):
        """Generate search queries to fill gaps."""
        queries = []
        
        for gap in gaps:
            if "skeptical" in gap:
                queries.append("critical analysis challenges objections")
            elif "apologetic" in gap:
                queries.append("harmonization coherence resolution")
            elif "Low confidence" in gap:
                # Extract key terms and search for more evidence
                queries.append(gap.split(":")[-1].strip())
        
        return queries
    
    def _has_converged(self, hypotheses):
        """Check if hypotheses have stabilized."""
        # Simple heuristic: at least one hypothesis >0.75 confidence
        return any(h.confidence > 0.75 for h in hypotheses)
```

---

## Phase 4: Testing & Validation

### Run Full Integration Test

```python
# tests/api/ai/test_reasoning_integration.py

def test_end_to_end_enhanced_reasoning(session):
    """Test full reasoning pipeline."""
    
    from theo.services.api.app.ai.rag.workflow_enhanced import ReasoningPipeline
    from theo.services.api.app.search.hybrid import search_passages
    
    # 1. Search for passages
    results = search_passages(session, query="Did Jesus claim to be divine?")
    
    # 2. Run enhanced reasoning
    pipeline = ReasoningPipeline(session, get_llm_registry(session))
    response = pipeline.compose_with_reasoning(
        question="Did Jesus claim to be divine?",
        results=results,
        mode="detective",
        enable_critique=True
    )
    
    # 3. Verify outputs
    assert 'chain_of_thought' in response
    assert len(response['chain_of_thought']['steps']) > 0
    assert 'fallacy_warnings' in response
    assert 'critique' in response
    assert response['critique']['quality'] >= 0
    assert response['critique']['quality'] <= 100
```

---

## Usage Examples

### Example 1: Basic Fallacy Check

```python
from theo.services.api.app.ai.reasoning.fallacies import detect_fallacies

answer = """
The early church clearly believed Jesus was divine. 
Famous scholars like N.T. Wright and Richard Bauckham say so.
Critics who disagree are biased liberals.
"""

warnings = detect_fallacies(answer)

for w in warnings:
    print(f"{w.fallacy_type} ({w.severity}): {w.description}")
    print(f"  Suggestion: {w.suggestion}\n")

# Output:
# verse_isolation (medium): Treating verse out of literary context
#   Suggestion: Consider the surrounding literary context and genre.
# appeal_to_authority (medium): Argument relies on authority without warrant  
#   Suggestion: Provide the underlying reasoning or evidence...
# ad_hominem (high): Attack on person rather than argument
#   Suggestion: Focus on evaluating the argument's logic...
```

### Example 2: Chain-of-Thought Generation

```python
# Generate detective-mode prompt
prompt = build_cot_prompt(
    question="What is Paul's view of the law in Galatians?",
    citations=citations,
    mode="detective"
)

# Send to LLM
completion = llm.generate(prompt)

# Parse reasoning
cot = parse_chain_of_thought(completion)

for step in cot.steps:
    print(f"{step.step_number}. {step.step_type.upper()}")
    print(f"   {step.content}\n")
```

### Example 3: Self-Critique

```python
from theo.services.api.app.ai.reasoning.metacognition import critique_reasoning

critique = critique_reasoning(
    reasoning_trace=chain_of_thought.raw_thinking,
    answer=model_output,
    citations=citations_list
)

print(f"Reasoning Quality: {critique.reasoning_quality}/100")

if critique.fallacies_found:
    print(f"\n⚠️ {len(critique.fallacies_found)} logical issues:")
    for f in critique.fallacies_found:
        print(f"  - {f.fallacy_type}: {f.description}")

if critique.recommendations:
    print("\n📋 Recommendations:")
    for rec in critique.recommendations:
        print(f"  - {rec}")
```

---

## Performance Considerations

### Token Usage

Chain-of-thought prompting uses **2-3x more tokens**:
- Basic prompt: ~500 tokens
- CoT prompt: ~1200 tokens
- CoT completion: ~800 tokens (vs ~300 basic)

**Mitigation:**
- Cache reasoning traces for identical questions
- Offer "fast mode" (basic) vs "deep mode" (CoT)
- User opt-in for autonomous exploration

### Latency

- Basic RAG: ~2-3 seconds
- CoT RAG: ~4-6 seconds
- Autonomous exploration (3 iterations): ~15-20 seconds

**Mitigation:**
- Stream reasoning steps as they're generated
- Show progress indicator during exploration
- Allow user to interrupt autonomous loops

### Costs

Autonomous exploration with 5 iterations:
- Retrieval: 5 queries × 10 passages = 50 passages
- Generation: 5 iterations × 1200 tokens = 6000 input tokens
- Output: 5 iterations × 800 tokens = 4000 output tokens

At GPT-4 pricing (~$0.03/1K input, ~$0.06/1K output):
- Single autonomous session: ~$0.42

**Mitigation:**
- Set budget limits per user/session
- Use cheaper models (GPT-3.5, Claude Instant) for iterations
- Cache aggressively

---

## Next Steps

1. ✅ **Review this implementation guide**
2. **Run database migration**
3. **Execute tests to verify modules work**
4. **Start with Phase 1 (fallacy detection integration)**
5. **Gather user feedback on reasoning traces**
6. **Iteratively add CoT, then autonomous exploration**
7. **Monitor performance and costs**
8. **Refine prompts based on theological accuracy**

---

## Support & Questions

- **Design doc:** `docs/AGENT_THINKING_ENHANCEMENT.md`
- **Module code:** `theo/infrastructure/api/app/ai/reasoning/`
- **Tests:** `tests/api/ai/test_reasoning_modules.py`
- **Migration:** `docs/migrations/add_reasoning_tables.sql`

For questions about implementation, check the test files for working examples.
