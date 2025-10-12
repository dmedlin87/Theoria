# AI Agent Thinking Scaffolding Enhancement

## Executive Summary

Transform the TheoEngine agent from a reactive RAG system into an autonomous theological detective that reasons, hypothesizes, critiques, and synthesizes like a human researcher.

## Current State Analysis

### Existing Capabilities

- **Contradiction Detection** (`contradictions.py`) - surfaces theological tensions with perspective filtering
- **RAG Guardrails** (`guardrails.py`) - validates citations, detects 23 safety patterns
- **Prompt Construction** (`prompts.py`) - basic system with adversarial scrubbing
- **Agent Trails** (`test_agent_evaluation.py`) - tracks steps, retrieval snapshots, token usage
- **Workflow Pipeline** (`workflow.py`) - retrieve → compose → validate

### Critical Gaps

1. **No logical fallacy detection** - agent can't critique its own reasoning
2. **No chain-of-thought scaffolding** - thinking is opaque, not stepwise
3. **No hypothesis generation** - agent doesn't form/test theories
4. **No autonomous research loops** - can't chase leads without user prompting
5. **No meta-cognitive reflection** - can't self-critique or revise
6. **No insight detection** - misses "aha!" moments in connections
7. **Contradiction data exists but isn't integrated into reasoning**
8. **No multi-perspective synthesis** - perspectives are filtered, not compared

---

## Enhancement Architecture

### Layer 1: Reasoning Primitives

#### 1.1 Logical Fallacy Detector

**Location:** `theo/services/api/app/ai/reasoning/fallacies.py`

Detect 20+ common fallacies in theological arguments:

- **Formal fallacies:** affirming consequent, denying antecedent, equivocation
- **Informal fallacies:** ad hominem, straw man, appeal to authority, circular reasoning
- **Theological-specific:** proof-texting, verse isolation, eisegesis markers, chronological snobbery

**Integration points:**

- Run on model completions before validation
- Run on retrieved passage claims during synthesis
- Expose via `/research/fallacies?claim={text}` endpoint
- Add `fallacy_warnings` to RAGAnswer model

#### 1.2 Chain-of-Thought Prompting

**Location:** `theo/services/api/app/ai/reasoning/chain_of_thought.py`

Force explicit reasoning steps:

```python
CHAIN_OF_THOUGHT_TEMPLATE = """
You are a theological researcher. Think step-by-step:

1. **Understand the Question:** Rephrase in your own words
2. **Identify Key Concepts:** List theological terms/frameworks needed
3. **Survey Evidence:** Note what passages support/contradict each position
4. **Detect Tensions:** Flag apparent contradictions
5. **Weigh Perspectives:** Consider skeptical, apologetic, neutral readings
6. **Check Reasoning:** Scan for logical fallacies
7. **Synthesize:** Form conclusion with explicit warrant chains
8. **Cite Sources:** Link every claim to OSIS+anchor

Question: {question}
Retrieved Passages: {passages}

Let's reason through this:
"""
```

**Enhancements:**

- Parse structured reasoning from `<thinking>` tags
- Store reasoning trace in `AgentStep.reasoning_trace` JSONB field
- Expose reasoning in UI with collapsible sections
- Allow users to challenge specific reasoning steps

#### 1.3 Hypothesis Generation & Testing

**Location:** `theo/services/api/app/ai/reasoning/hypotheses.py`

Enable agent to form/test theories:

```python
@dataclass
class Hypothesis:
    id: str
    claim: str
    confidence: float  # 0.0 - 1.0
    supporting_passages: list[PassageRef]
    contradicting_passages: list[PassageRef]
    fallacy_warnings: list[str]
    perspective_scores: dict[str, float]  # skeptical/apologetic/neutral
    
def generate_hypotheses(question: str, passages: list) -> list[Hypothesis]:
    """Extract 2-4 competing hypotheses from evidence"""
    
def test_hypothesis(hyp: Hypothesis, session: Session) -> HypothesisTest:
    """Retrieve additional passages to confirm/refute"""
```

**Workflow:**

1. User asks question → agent generates 2-4 hypotheses
2. For each hypothesis, agent autonomously searches for supporting/contradicting evidence
3. Agent scores confidence using Bayesian updating
4. Agent presents ranked hypotheses with explicit reasoning chains

---

### Layer 2: Autonomous Research Loop

#### 2.1 Self-Directed Exploration

**Location:** `theo/services/api/app/ai/agents/explorer.py`

Agent autonomously chases leads:

```python
class AutonomousExplorer:
    def explore(self, initial_question: str, max_iterations: int = 5):
        """
        1. Form initial hypotheses
        2. Identify knowledge gaps
        3. Generate follow-up queries to fill gaps
        4. Retrieve new evidence
        5. Update hypotheses
        6. Repeat until convergence or max iterations
        """
```

**Stopping conditions:**

- Confidence threshold reached (>0.85)
- No new passages found
- Contradiction count stabilizes
- Max iterations hit

**Safety guardrails:**

- Log every retrieval step in AgentTrail
- Enforce retrieval budget (max 50 passages per session)
- User can interrupt/redirect at any step
- All reasoning traces visible in real-time

#### 2.2 Knowledge Gap Detection

Prompt augmentation:

```text
After reviewing the evidence, what critical information is missing?
- Which perspectives are underrepresented?
- Which time periods lack sources?
- Which authors should weigh in but don't appear?
- What background context would clarify tensions?

Generate 2-3 follow-up search queries to fill these gaps.
```

---

### Layer 3: Meta-Cognitive Reflection

#### 3.1 Self-Critique Module

**Location:** `theo/services/api/app/ai/reasoning/metacognition.py`

Agent critiques its own reasoning:

```python
def critique_reasoning(reasoning_trace: dict, answer: str) -> Critique:
    """
    Apply adversarial review:
    - Check for logical fallacies
    - Verify citation grounding
    - Test alternative interpretations
    - Identify confirmation bias
    - Score reasoning quality (0-100)
    """
```

**Prompt pattern:**

```text
You are a theological skeptic reviewing this reasoning:

{reasoning_trace}

Critique:
1. What logical fallacies appear?
2. Which citations are weakly connected to claims?
3. What alternative explanations were ignored?
4. Is there confirmation bias toward a perspective?
5. Rate reasoning quality: [0-100]
```

#### 3.2 Revision Loop

After critique, agent can revise:

1. Re-retrieve with different filters
2. Regenerate answer addressing critique
3. Compare original vs. revised
4. Present both to user with explanation

---

### Layer 4: Multi-Perspective Synthesis

#### 4.1 Perspective Orchestrator

**Location:** `theo/services/api/app/ai/reasoning/perspectives.py`

Current system filters by perspective - enhancement synthesizes across them:

```python
class PerspectiveSynthesizer:
    def synthesize(self, question: str) -> PerspectiveSynthesis:
        # Run same question through 3 lenses
        skeptical_view = self._generate_with_filter("skeptical")
        apologetic_view = self._generate_with_filter("apologetic")
        neutral_view = self._generate_with_filter("neutral")
        
        # Identify agreements vs. tensions
        consensus = self._find_common_ground([skeptical, apologetic, neutral])
        tensions = self._map_disagreements([skeptical, apologetic, neutral])
        
        # Generate meta-analysis
        synthesis = self._synthesize_perspectives(consensus, tensions)
        
        return PerspectiveSynthesis(
            consensus_points=consensus,
            tension_map=tensions,
            meta_analysis=synthesis,
            perspective_views={"skeptical": skeptical_view, ...}
        )
```

**UI Enhancement:**

- Tabbed interface showing each perspective
- Venn diagram of consensus vs. unique claims
- Highlight where perspectives diverge
- "Synthesis" tab with meta-analysis

#### 4.2 Contradiction Integration

Connect existing contradiction seeds into reasoning:

```python
# In chain-of-thought workflow
def enrich_with_contradictions(osis: str, session: Session) -> dict:
    # Fetch contradiction seeds for this verse
    contradictions = search_contradictions(session, osis=osis)
    
    # Inject into prompt
    prompt += "\n\nKnown Tensions:\n"
    for contra in contradictions:
        prompt += f"- {contra.summary} ({contra.osis_a} vs {contra.osis_b})\n"
        prompt += f"  Perspective: {contra.perspective}\n"
    
    prompt += "\nAddress these tensions in your reasoning.\n"
```

---

### Layer 5: Insight Detection

#### 5.1 "Aha!" Moment Detector

**Location:** `theo/services/api/app/ai/reasoning/insights.py`

Detect when agent makes novel connections:

```python
@dataclass
class Insight:
    id: str
    insight_type: str  # "cross_ref" | "pattern" | "synthesis" | "tension_resolution"
    description: str
    supporting_passages: list[PassageRef]
    novelty_score: float  # how rare is this connection?
    
def detect_insights(reasoning_trace: dict, passages: list) -> list[Insight]:
    """
    Patterns indicating insights:
    - Cross-reference between distant OSIS ranges
    - Connection between authors who don't usually interact
    - Synthesis across >3 perspectives
    - Novel resolution of known contradiction
    - Pattern across >5 passages from different sources
    """
```

**Prompt injection:**

```text
As you reason, explicitly mark insights:
<insight type="cross_ref">
Matthew 5:17 and Romans 10:4 create a tension about Torah's end...
</insight>
```

**UI:**

- Highlight insights with 💡 icon
- "Insights" panel summarizing discoveries
- Allow users to save insights as notes
- Track insight patterns over time

#### 5.2 Pattern Recognition

Detect recurring themes across corpus:

- Same verse cited by 10+ authors → flag as "theological anchor"
- Contradiction pair appears 5+ times → "hotly debated"
- Author consistently opposes specific tradition → "contrarian signal"
- Emerging topic in recent ingests → "trending theme"

---

### Layer 6: Enhanced Prompting Strategies

#### 6.1 Role-Based Personas

Define detective personas with specialized prompts:

**Detective Mode:**

```text
You are a theological detective investigating: {question}

Method:
1. Gather evidence (passages)
2. Look for fingerprints (citation patterns, word choice, theological frameworks)
3. Interview witnesses (multiple authors/perspectives)
4. Reconstruct timeline (chronological development of doctrine)
5. Build case (synthesize with warrant chains)
6. Present findings (answer with reasoning trace)
```

**Critic Mode:**

```text
You are a skeptical peer reviewer. Your job is to poke holes:
- Question every claim
- Demand stronger evidence
- Surface alternative explanations
- Check for logical fallacies
- Rate argument strength: [F to A+]
```

**Apologist Mode:**

```text
You are seeking coherence and harmony:
- Find ways passages complement each other
- Surface background context that resolves tensions
- Identify translation/interpretation issues
- Build strongest case for consistency
```

**Synthesizer Mode:**

```text
You are a neutral academic surveying the field:
- Map full spectrum of scholarly positions
- Identify consensus vs. disputed claims
- Trace historical development
- Present state of the question fairly
```

#### 6.2 Socratic Questioning

Agent asks clarifying questions before diving in:

```text
Before I research this, let me clarify:
1. Are you asking about [interpretation A] or [interpretation B]?
2. Should I focus on [time period] or survey all eras?
3. Do you want skeptical challenges or harmonization attempts?
4. Should I trace historical development or just current views?
```

---

### Layer 7: Integration Architecture

#### 7.1 Enhanced Workflow Pipeline

**Location:** `theo/services/api/app/ai/rag/workflow_v2.py`

```python
class ReasoningPipeline(GuardedAnswerPipeline):
    def compose_with_reasoning(
        self,
        question: str,
        mode: str = "detective",  # detective|critic|apologist|synthesizer
        autonomous: bool = False,
        max_iterations: int = 3,
    ) -> ReasoningAnswer:
        # 1. Initial retrieval
        results = search_passages(self.session, query=question)
        
        # 2. Generate initial hypotheses
        hypotheses = generate_hypotheses(question, results)
        
        # 3. If autonomous, run exploration loop
        if autonomous:
            for i in range(max_iterations):
                gaps = detect_knowledge_gaps(hypotheses)
                if not gaps:
                    break
                new_results = self._fill_gaps(gaps)
                results.extend(new_results)
                hypotheses = update_hypotheses(hypotheses, new_results)
        
        # 4. Enrich with contradiction data
        osis_refs = extract_osis_from_question(question)
        contradictions = search_contradictions(self.session, osis=osis_refs)
        
        # 5. Generate with chain-of-thought
        prompt = build_reasoning_prompt(
            question=question,
            passages=results,
            contradictions=contradictions,
            mode=mode,
            hypotheses=hypotheses
        )
        
        answer = self._generate_with_cot(prompt)
        
        # 6. Extract reasoning trace
        reasoning_trace = parse_reasoning_trace(answer.model_output)
        
        # 7. Detect fallacies
        fallacies = detect_fallacies(reasoning_trace)
        
        # 8. Detect insights
        insights = detect_insights(reasoning_trace, results)
        
        # 9. Self-critique
        critique = critique_reasoning(reasoning_trace, answer.model_output)
        
        # 10. Return enhanced answer
        return ReasoningAnswer(
            answer=answer,
            reasoning_trace=reasoning_trace,
            hypotheses=hypotheses,
            fallacy_warnings=fallacies,
            insights=insights,
            critique=critique,
            exploration_steps=i if autonomous else 0
        )
```

#### 7.2 Database Extensions

Add tables to track reasoning:

```sql
-- Reasoning traces
CREATE TABLE reasoning_traces (
  id UUID PRIMARY KEY,
  trail_id UUID REFERENCES agent_trails(id),
  step_index INT,
  reasoning_type TEXT, -- 'hypothesis'|'critique'|'synthesis'
  content JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Insights
CREATE TABLE insights (
  id UUID PRIMARY KEY,
  trail_id UUID REFERENCES agent_trails(id),
  insight_type TEXT,
  description TEXT,
  passage_ids UUID[],
  novelty_score REAL,
  user_feedback TEXT, -- user can rate insight quality
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Hypotheses
CREATE TABLE hypotheses (
  id UUID PRIMARY KEY,
  trail_id UUID REFERENCES agent_trails(id),
  claim TEXT,
  confidence REAL,
  supporting_passage_ids UUID[],
  contradicting_passage_ids UUID[],
  status TEXT, -- 'active'|'confirmed'|'refuted'
  created_at TIMESTAMPTZ DEFAULT now()
);
```

---

### Layer 8: UI Enhancements

#### 8.1 Reasoning Viewer

New UI component: `ReasoningTrace.tsx`

- Expandable tree view of reasoning steps
- Each node shows: claim → evidence → warrant
- Color-coded by confidence (red=low, yellow=medium, green=high)
- Click passage reference to view in context
- Highlight fallacy warnings in orange

#### 8.2 Hypothesis Dashboard

- Card view of competing hypotheses
- Confidence bars showing relative strength
- Supporting vs. contradicting evidence counts
- "Test Hypothesis" button triggers autonomous exploration
- Live updates as agent gathers evidence

#### 8.3 Insight Feed

- Timeline of insights discovered
- Filter by type (cross_ref, pattern, synthesis, etc.)
- "Save to Notes" quick action
- Share insight with team
- Track which insights led to publications

---

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)

1. Create `reasoning` module structure
2. Implement logical fallacy detector
3. Build chain-of-thought prompt templates
4. Add reasoning trace parsing
5. Extend database schema
6. Add tests for fallacy detection

### Phase 2: Autonomous Exploration (Weeks 3-4)

1. Implement hypothesis generation
2. Build autonomous explorer loop
3. Add knowledge gap detection
4. Implement stopping conditions
5. Add safety guardrails (retrieval budgets)
6. Create exploration UI

### Phase 3: Meta-Cognition (Weeks 5-6)

1. Implement self-critique module
2. Build revision loop
3. Add perspective synthesizer
4. Integrate contradiction data into reasoning
5. Add multi-perspective UI tabs

### Phase 4: Insight Detection (Weeks 7-8)

1. Implement insight detector
2. Add pattern recognition
3. Build novelty scoring
4. Create insight feed UI
5. Add user feedback mechanisms

### Phase 5: Polish & Evaluation (Weeks 9-10)

1. Build reasoning trace viewer
2. Add hypothesis dashboard
3. Implement role-based personas
4. Create evaluation harness
5. Run red-team testing
6. Performance optimization

---

## Evaluation Framework

### Reasoning Quality Metrics

- **Logical coherence:** % of reasoning chains free of fallacies
- **Evidence grounding:** % of claims backed by citations
- **Perspective balance:** Distribution across skeptical/apologetic/neutral
- **Insight novelty:** % of connections not in training data
- **Hypothesis accuracy:** % of predictions confirmed by evidence
- **Critique quality:** Inter-rater reliability with human theologians

### User Experience Metrics

- **Time to insight:** How quickly users find "aha!" moments
- **Exploration depth:** Avg autonomous iterations before convergence
- **Reasoning clarity:** User ratings of trace understandability
- **Trust signals:** % of users who verify citations vs. trust blindly
- **Revision impact:** Quality improvement from critique loop

### Safety Metrics

- **Retrieval budget adherence:** % of sessions staying under limits
- **Guardrail pass rate:** % of autonomous generations passing validation
- **Fallacy detection recall:** % of planted fallacies caught
- **Runaway prevention:** Max iterations hit before stopping

---

## Example Workflows

### Workflow 1: Autonomous Theological Detective

```text
User: "Did the early church believe Jesus was divine?"

Agent:
[Generating hypotheses...]
H1: Early church unanimously affirmed divinity (confidence: 0.3)
H2: Belief developed gradually over 1st-3 centuries (confidence: 0.5)
H3: Dispute remained unresolved until Nicaea (confidence: 0.4)

[Exploring evidence...]
Iteration 1: Searching for "early church Jesus divinity"
  Found: 12 passages (Ignatius, Polycarp, Justin Martyr)
  Updated confidence: H1=0.4, H2=0.6, H3=0.3

Iteration 2: Knowledge gap - missing Arian perspective
  Searching for "Arius subordination Logos"
  Found: 8 passages
  Updated confidence: H1=0.3, H2=0.7, H3=0.5

Iteration 3: Knowledge gap - missing NT basis
  Searching for "John 1 Philippians 2 divinity"
  Found: 15 passages
  Updated confidence: H1=0.4, H2=0.75, H3=0.4

[Converged after 3 iterations]

[Synthesizing...]
<thinking>
1. Evidence shows gradual development pattern
2. NT texts provide foundation but ambiguity exists
3. 2nd-century fathers build on NT in Christological direction
4. Arian controversy shows dispute persisted to 4th century
5. Synthesis: Belief trajectory emerged early but formalization took centuries
</thinking>

<insight type="synthesis">
The divine-human Christology wasn't a 4th-century invention but
a trajectory present in NT texts (esp. John's prologue), amplified
by apostolic fathers, and crystallized through Arian controversy.
</insight>

[Citations: John 1:1-18, Ignatius Romans 6:3, Arius Letter to Eusebius, Athanasius Contra Arianos...]

[Critique:]
- Reasoning quality: 85/100
- Fallacies detected: None
- Gaps: Could strengthen with more pre-Nicene evidence
- Bias check: Slightly favors apologetic interpretation (0.6 vs 0.4 skeptical)
```

### Workflow 2: Socratic Clarification

```text
User: "What does Paul say about the law?"

Agent: Before I research this, let me clarify:
1. Do you mean (A) Torah observance for Christians, or (B) law vs. grace soteriology?
2. Should I focus on Romans/Galatians or survey all Pauline letters?
3. Are you asking about Paul's own view or later interpretations of Paul?

[User selects A, all letters, Paul's view]

Agent: [Proceeds with focused research...]
```

---

## Technical Considerations

### Performance

- **Streaming responses:** Yield reasoning steps as generated, don't wait for completion
- **Caching:** Cache hypothesis tests, reasoning traces, critique results
- **Batching:** Group fallacy detection across all claims in single pass
- **Async:** Run perspective synthesis in parallel (3 concurrent generations)

### Costs

- **Token multiplication:** Chain-of-thought uses 2-3x tokens vs. direct answer
- **Autonomous loops:** Each iteration adds retrieval + generation cost
- **Mitigation:** User opt-in for autonomous mode; budget controls; cache aggressively

### Safety

- **Runaway prevention:** Hard limits on iterations (max 10)
- **Retrieval bounds:** Max 50 passages per session
- **User control:** Interrupt button visible during autonomous exploration
- **Transparency:** Every step logged in AgentTrail for auditability

---

## Next Steps

1. **Review this design** with team/stakeholders
2. **Prioritize phases** - start with Phase 1 foundation
3. **Build MVP** - Implement fallacy detector + chain-of-thought first
4. **User testing** - Get feedback on reasoning trace UI
5. **Iterate** - Refine prompts based on real theological questions
6. **Scale** - Optimize performance before rolling out autonomous mode

---

**Document Status:** Draft v1.0  
**Author:** AI Agent Enhancement Team  
**Last Updated:** 2025-01-12
