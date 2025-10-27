> **Archived on 2025-10-26**

# Agent & Prompting Architecture in Theoria

## Overview

Theoria uses a **multi-layered agent architecture** that combines RAG (Retrieval-Augmented Generation), chain-of-thought reasoning, and specialized prompting strategies to provide grounded theological research assistance. The system is designed to be **evidence-first**, **transparent**, and **self-critical**.

---

## Core Philosophy

### 1. **Evidence-First, Never Hallucinate**
- Every claim must be backed by citations (OSIS references + document anchors)
- Adversarial scrubbing prevents prompt injection and unsafe instructions
- Guardrails validate citations and detect safety violations

### 2. **Transparent Reasoning**
- Chain-of-thought scaffolding makes reasoning explicit
- Agent trails log every retrieval, generation, and validation step
- Users can inspect and challenge reasoning at any step

### 3. **Self-Critical & Multi-Perspective**
- Fallacy detection scans for logical errors
- Meta-cognitive critique evaluates reasoning quality
- Multi-perspective synthesis compares skeptical, apologetic, and neutral views

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACE                            │
│  (Chat, Research, Discoveries, Settings)                     │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│              AGENT ORCHESTRATOR (TRO)                        │
│  - Routes requests to appropriate workflow                   │
│  - Manages model selection (GPT-5, GPT-5-mini, o3)          │
│  - Enforces output schemas and validation                    │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
┌───────▼──────┐ ┌─────▼──────┐ ┌─────▼──────────┐
│  RAG Layer   │ │ Reasoning  │ │  Discovery     │
│              │ │  Layer     │ │  Engine        │
│ - Retrieval  │ │ - CoT      │ │ - Patterns     │
│ - Prompts    │ │ - Fallacy  │ │ - Gaps         │
│ - Guardrails │ │ - Hypotheses│ │ - Insights    │
│ - Citations  │ │ - Critique │ │ - Trends       │
└──────┬───────┘ └─────┬──────┘ └────┬───────────┘
       │               │              │
       └───────────────┴──────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│         KNOWLEDGE BASE                          │
│  - PostgreSQL + pgvector                        │
│  - Document embeddings                          │
│  - Contradiction seeds                          │
│  - Agent trails & reasoning traces              │
└─────────────────────────────────────────────────┘
```

---

## Layer 1: RAG (Retrieval-Augmented Generation)

### Location
- `theo/services/api/app/ai/rag/`

### Components

#### 1.1 Prompt Construction (`prompts.py`)

**Purpose:** Build safe, structured prompts with adversarial scrubbing

**Key Features:**
- **Adversarial filtering** - Removes prompt injection attempts
  - "ignore previous instructions" → `[filtered-instruction]`
  - "override guardrails" → `[filtered-override]`
  - SQL injection, XSS, script tags → filtered
- **Citation formatting** - Structures passages with OSIS + anchors
- **Memory context** - Includes conversation history when relevant

**Example:**
```python
from theo.infrastructure.api.app.ai.rag.prompts import PromptContext, scrub_adversarial_language

# Build a safe prompt
context = PromptContext(
    citations=[...],  # Retrieved passages
    memory_context=["Prior question: Was Jesus divine?"]
)

prompt = context.build_prompt("What did Paul teach about the law?")
# Output:
# You are Theo Engine's grounded assistant.
# Answer the question strictly from the provided passages.
# Cite evidence using the bracketed indices and retain OSIS + anchor in a Sources line.
# ...
# Question: What did Paul teach about the law?
# Passages:
# [1] For by grace you have been saved... (OSIS Eph.2.8, page 42)
# [2] The law was our guardian... (OSIS Gal.3.24, page 58)
```

#### 1.2 Guardrails (`guardrails.py`)

**Purpose:** Validate model outputs for safety and quality

**23 Safety Patterns Detected:**
- Prompt injection attempts
- Citation fabrication
- Theological bias extremes
- Unsafe content (violence, hate speech)
- Privacy violations
- Misinformation markers

**Validation Checks:**
- All citations must exist in corpus
- OSIS references must be valid
- Confidence scores must be justified
- No hallucinated sources

#### 1.3 Workflow Pipeline (`workflow.py`)

**Standard RAG Flow:**
1. **Retrieve** - Hybrid search (semantic + keyword) over corpus
2. **Compose** - Generate answer using retrieved passages
3. **Validate** - Run guardrails and citation checks
4. **Return** - Structured answer with citations and metadata

---

## Layer 2: Reasoning Framework

### Location
- `theo/services/api/app/ai/reasoning/`

### Components

#### 2.1 Chain-of-Thought (`chain_of_thought.py`)

**Purpose:** Force explicit, step-by-step reasoning

**4 Reasoning Modes:**

##### Detective Mode
```text
You are a theological detective investigating this question.

Detective Method:
1. Understand the Question: Rephrase in your own words
2. Identify Key Concepts: List theological terms/frameworks needed
3. Survey Evidence: Examine each passage for support/challenge
4. Detect Tensions: Flag contradictions or competing interpretations
5. Weigh Perspectives: Consider skeptical, apologetic, neutral readings
6. Check Reasoning: Scan for logical fallacies
7. Synthesize: Form conclusion with explicit warrant chains
8. Cite Sources: Link every claim to passages using [index] format

<thinking>
[Step-by-step reasoning here]
</thinking>

Answer: [Your conclusion]
```

##### Critic Mode
```text
You are a skeptical peer reviewer. Your job is to poke holes:
- Question every claim
- Demand stronger evidence
- Surface alternative explanations
- Check for logical fallacies
- Rate argument strength: [F to A+]
```

##### Apologist Mode
```text
You are seeking coherence and harmony:
- Find ways passages complement each other
- Surface background context that resolves tensions
- Identify translation/interpretation issues
- Build strongest case for consistency
```

##### Synthesizer Mode
```text
You are a neutral academic surveying the field:
- Map full spectrum of scholarly positions
- Identify consensus vs. disputed claims
- Trace historical development
- Present state of the question fairly
```

**Usage:**
```python
from theo.infrastructure.api.app.ai.reasoning.chain_of_thought import build_cot_prompt

prompt = build_cot_prompt(
    question="Did the early church believe Jesus was divine?",
    citations=[...],
    mode="detective",  # or "critic", "apologist", "synthesizer"
    contradictions=[...]  # Optional known tensions
)
```

#### 2.2 Fallacy Detection (`fallacies.py`)

**Purpose:** Detect logical errors in reasoning

**9 Fallacy Types Detected:**

1. **Ad Hominem** - Attacking person instead of argument
   - "Ehrman is biased, so his argument is wrong"
   
2. **Straw Man** - Misrepresenting opponent's position
   - "Critics claim Jesus never existed" (when they claim something more nuanced)

3. **Appeal to Authority** - Uncritical citation of experts
   - "Scholar X says Y, therefore Y is true"

4. **Circular Reasoning** - Conclusion assumes premise
   - "The Bible is true because it says so"

5. **False Dilemma** - Only two options when more exist
   - "Either Jesus was divine or he was a liar"

6. **Proof-Texting** - Cherry-picking verses out of context
   - Citing 10+ verses without synthesis

7. **Equivocation** - Using same word with different meanings
   - "Law" meaning Torah vs. moral principle

8. **Chronological Snobbery** - Dismissing old sources as outdated
   - "That's a 2nd-century view, so it's wrong"

9. **Eisegesis** - Reading into text what isn't there
   - Markers: "clearly", "obviously", "must mean"

**Usage:**
```python
from theo.infrastructure.api.app.ai.reasoning.fallacies import detect_fallacies

text = "Ehrman is biased, so his argument about Jesus's divinity is wrong."
warnings = detect_fallacies(text)

for warning in warnings:
    print(f"{warning.fallacy_type} ({warning.severity})")
    print(f"  {warning.description}")
    print(f"  Suggestion: {warning.suggestion}")
```

#### 2.3 Hypothesis Generation (`hypotheses.py`)

**Purpose:** Form and test competing theories

**Workflow:**
1. **Generate** - Extract 2-4 competing hypotheses from evidence
2. **Test** - Autonomously search for supporting/contradicting passages
3. **Score** - Update confidence using Bayesian reasoning
4. **Present** - Rank hypotheses with explicit reasoning chains

**Data Model:**
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
```

**Example:**
```python
from theo.infrastructure.api.app.ai.reasoning.hypotheses import generate_hypotheses

hypotheses = generate_hypotheses(
    question="Did the early church believe Jesus was divine?",
    passages=[...]
)

# Output:
# H1: Early church unanimously affirmed divinity (confidence: 0.3)
# H2: Belief developed gradually over 1st-3 centuries (confidence: 0.7)
# H3: Dispute remained unresolved until Nicaea (confidence: 0.4)
```

#### 2.4 Insight Detection (`insights.py`)

**Purpose:** Auto-discover novel connections

**6 Insight Types:**
- **Cross-reference** - Connections between distant OSIS ranges
- **Pattern** - Recurring themes across 5+ passages
- **Synthesis** - Integration across 3+ perspectives
- **Tension resolution** - Novel resolution of known contradiction
- **Author connection** - Links between authors who don't usually interact
- **Trend** - Emerging topic in recent ingests

**Example:**
```python
@dataclass
class Insight:
    id: str
    insight_type: str  # "cross_ref" | "pattern" | "synthesis" | ...
    description: str
    supporting_passages: list[PassageRef]
    novelty_score: float  # How rare is this connection?
```

#### 2.5 Meta-Cognition (`metacognition.py`)

**Purpose:** Self-critique and revision

**Critique Process:**
1. **Review reasoning trace** - Parse chain-of-thought steps
2. **Check fallacies** - Run fallacy detector on reasoning
3. **Verify citations** - Ensure all claims are grounded
4. **Test alternatives** - Consider competing interpretations
5. **Detect bias** - Check for confirmation bias toward a perspective
6. **Score quality** - Rate reasoning 0-100

**Revision Loop:**
- If critique score < 70, agent can revise
- Re-retrieve with different filters
- Regenerate answer addressing critique
- Compare original vs. revised
- Present both to user with explanation

#### 2.6 Multi-Perspective Synthesis (`perspectives.py`)

**Purpose:** Compare skeptical, apologetic, and neutral views

**Workflow:**
1. **Run same question through 3 lenses**
   - Skeptical filter (critical scholarship)
   - Apologetic filter (harmonization attempts)
   - Neutral filter (balanced survey)

2. **Identify agreements vs. tensions**
   - Consensus points (all 3 agree)
   - Tension map (where they diverge)

3. **Generate meta-analysis**
   - Synthesize across perspectives
   - Highlight where evidence is strong vs. disputed

**UI Enhancement:**
- Tabbed interface showing each perspective
- Venn diagram of consensus vs. unique claims
- "Synthesis" tab with meta-analysis

---

## Layer 3: Theoria Research Orchestrator (TRO)

### Location
- `docs/theoria_instruction_prompt.md`

### Purpose
Master instruction prompt that orchestrates all agent behaviors

### Key Directives

#### Identity
```text
You are Theoria Research Orchestrator (TRO), an evidence-first research agent 
for historical-critical theology. Your job is to:

* Produce structured artifacts with verifiable citations
* Run end-to-end passes: RAG → synthesis → citations → validations
* Prefer facts over flourish. Never invent citations or sources.
* Preserve non-regression: do not drop features, depth, or checks
```

#### Model Selection Policy
- **GPT-5** - Flagship for long, messy, multi-doc synthesis; agentic flows; final analyses
- **GPT-5 mini** - Fast/cheap for day-to-day dev, schema validation, tool orchestrations
- **o3-deep-research** - Exhaustive literature sweeps with links; background mode

#### Built-in Tools (via Responses API)
- **web_search** - Fetch fresh scholarship/sources for citations
- **file_search** - Hybrid retrieval over uploaded PDFs/notes
- **code_interpreter** - Python sandbox for computing stability scores, charts
- **computer_use** - Stepwise browse/click/copy for verifiable UI actions
- **image_generation** - Quick explanatory diagrams (timelines, claim graphs)

#### Custom Tools (Function Calling)
1. `resolve_verse({ book, chapter, verse_start, verse_end, translation })`
2. `lookup_canon({ topic, tradition, range, notes_ok })`
3. `score_citation({ url, claim_id, criteria, weights })`
4. `dedupe_passages({ passage_ids[] })`
5. `stability_metrics({ evidence_card })`

#### Output Contracts (Schemas)

**EvidenceCard:**
```json
{
  "id": "string",
  "claim": "string",
  "mode": "Apologetic|Neutral|Skeptical",
  "citations": [
    {
      "title": "string",
      "url": "uri",
      "source_type": "primary|secondary|tertiary",
      "accessed": "date",
      "excerpt": "string"
    }
  ],
  "evidence_points": ["string"],
  "counter_evidence": ["string"],
  "stability": {
    "score": 0.0-1.0,
    "components": {
      "attestation": 0.0-1.0,
      "consensus": 0.0-1.0,
      "recency_risk": 0.0-1.0,
      "textual_variants": 0.0-1.0
    }
  },
  "confidence": 0.0-1.0,
  "open_questions": ["string"]
}
```

**Contradiction:**
```json
{
  "id": "string",
  "passage_a": "string",
  "passage_b": "string",
  "conflict_type": "chronology|genealogy|event|speech|law|number|title",
  "notes": "string",
  "graph_edges": [{"from": "string", "to": "string", "weight": 0.0-1.0}]
}
```

#### Runbook (Default Pass)
1. **Outline** what you will produce and which tools you'll use
2. **Retrieve**: `file_search` (internal) → `web_search` (external) when needed
3. **Assemble sources table** (citation candidates with URLs, dates, credibility)
4. **Synthesis**: argue with sources; call custom tools as needed
5. **Validate/Score**: run `code_interpreter`/`stability_metrics`; ensure schema compliance
6. **Deliver artifacts** (JSON) + human-readable summary + optional diagram
7. **Log everything** in `run_logs`

---

## Layer 4: Agent Trails & Observability

### Location
- `theo/services/api/app/ai/trails.py`
- Database: `agent_trails`, `agent_steps`, `reasoning_traces` tables

### Purpose
Track every agent action for transparency and debugging

### Data Model

```sql
-- Agent trail (one per research session)
CREATE TABLE agent_trails (
  id UUID PRIMARY KEY,
  user_id UUID,
  mode TEXT,  -- 'detective', 'critic', 'apologist', 'synthesizer'
  plan_md TEXT,
  final_md TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Agent steps (one per tool call or generation)
CREATE TABLE agent_steps (
  trail_id UUID REFERENCES agent_trails(id),
  step_index INT,
  tool TEXT,  -- 'retrieve', 'generate', 'validate', 'critique'
  args_json JSONB,
  output_digest TEXT,
  tokens_in INT,
  tokens_out INT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Reasoning traces (parsed chain-of-thought)
CREATE TABLE reasoning_traces (
  id UUID PRIMARY KEY,
  trail_id UUID REFERENCES agent_trails(id),
  step_index INT,
  reasoning_type TEXT,  -- 'hypothesis', 'critique', 'synthesis'
  content JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Insights (novel connections discovered)
CREATE TABLE insights (
  id UUID PRIMARY KEY,
  trail_id UUID REFERENCES agent_trails(id),
  insight_type TEXT,
  description TEXT,
  passage_ids UUID[],
  novelty_score REAL,
  user_feedback TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Hypotheses (competing theories)
CREATE TABLE hypotheses (
  id UUID PRIMARY KEY,
  trail_id UUID REFERENCES agent_trails(id),
  claim TEXT,
  confidence REAL,
  supporting_passage_ids UUID[],
  contradicting_passage_ids UUID[],
  status TEXT,  -- 'active', 'confirmed', 'refuted'
  created_at TIMESTAMPTZ DEFAULT now()
);
```

### Features
- **Replay** - Re-run same trail against newer datasets
- **Audit** - Inspect every retrieval, generation, validation step
- **Debug** - Trace why agent made specific decisions
- **Evaluate** - Measure reasoning quality over time

---

## Prompting Best Practices

### 1. **Structured Prompts**
Always use explicit sections and numbered steps:
```text
**Question:** [user question]

**Evidence:**
[1] passage 1
[2] passage 2

**Method:**
1. Step 1
2. Step 2

**Format:**
<thinking>[reasoning]</thinking>
Answer: [conclusion]
```

### 2. **Adversarial Robustness**
- Scrub user input for injection attempts
- Filter unsafe instructions before LLM sees them
- Validate outputs against schemas

### 3. **Citation Discipline**
- Every claim must link to [index] in passages
- Include OSIS reference + document anchor
- Validate citations exist in corpus

### 4. **Confidence Calibration**
- Use 0.0-1.0 scale with explicit rationale
- Low confidence (< 0.5) = "evidence is mixed"
- High confidence (> 0.8) = "strong consensus"

### 5. **Perspective Balance**
- Run same question through multiple lenses
- Highlight where perspectives agree vs. diverge
- Avoid categorical language where evidence is disputed

### 6. **Fallacy Prevention**
- Run fallacy detector on all outputs
- Flag high-severity warnings to user
- Suggest revisions when fallacies detected

### 7. **Iterative Refinement**
- Use critique loop for important questions
- Compare original vs. revised answers
- Learn from critique patterns over time

---

## Example Workflows

### Workflow 1: Simple RAG Query

**User:** "What does Paul say about the law?"

**Agent Process:**
1. **Retrieve** - Hybrid search for "Paul law" → 15 passages
2. **Prompt** - Build basic RAG prompt with citations
3. **Generate** - LLM produces answer with [index] citations
4. **Validate** - Guardrails check citations, safety patterns
5. **Return** - Answer + sources + metadata

**Output:**
```text
Paul's view of the law is complex. In Romans 7:12, he affirms "the law is holy" [1], 
but in Galatians 3:24, he describes it as a "guardian until Christ came" [2], 
suggesting its role was temporary. He emphasizes that justification comes through 
faith, not law observance (Rom 3:28) [3].

Sources:
[1] Romans 7:12 (OSIS Rom.7.12, Commentary page 142)
[2] Galatians 3:24 (OSIS Gal.3.24, Commentary page 58)
[3] Romans 3:28 (OSIS Rom.3.28, Commentary page 89)
```

### Workflow 2: Detective Mode with Chain-of-Thought

**User:** "Did the early church believe Jesus was divine?"

**Agent Process:**
1. **Retrieve** - Search "early church Jesus divinity" → 20 passages
2. **Generate Hypotheses**
   - H1: Unanimous affirmation (confidence: 0.3)
   - H2: Gradual development (confidence: 0.7)
   - H3: Unresolved until Nicaea (confidence: 0.4)
3. **Chain-of-Thought Reasoning** (Detective Mode)
   ```
   <thinking>
   1. Understand: Question asks about early church belief (1st-4th century)
   2. Identify: Key concepts - divinity, Christology, Nicaea, Arian controversy
   3. Survey: 
      - NT texts show high Christology (John 1:1, Phil 2:6-11)
      - Ignatius (110 AD) calls Jesus "God" explicitly
      - Arius (320 AD) disputes full divinity
   4. Detect: Tension between NT foundation and later disputes
   5. Weigh: 
      - Apologetic: Belief was early and consistent
      - Skeptical: Development took centuries
      - Neutral: Trajectory present but formalization gradual
   6. Check: No fallacies detected
   7. Synthesize: H2 (gradual development) best fits evidence
   </thinking>
   ```
4. **Insight Detection**
   - Cross-reference: John's prologue → Ignatius → Nicaea trajectory
   - Pattern: "God" language increases over time
5. **Critique** - Score: 85/100 (strong reasoning, well-cited)
6. **Return** - Answer + reasoning trace + hypotheses + insights

### Workflow 3: Multi-Perspective Synthesis

**User:** "Was Jesus's tomb empty?"

**Agent Process:**
1. **Retrieve** - Search "empty tomb resurrection" → 25 passages
2. **Run 3 Perspectives in Parallel**
   - **Apologetic View**
     - Empty tomb is historical fact
     - Multiple attestation (all 4 gospels)
     - Best explains early Christian belief
   - **Skeptical View**
     - Empty tomb is later legend
     - Mark's ending (16:8) is ambiguous
     - Paul doesn't mention empty tomb
   - **Neutral View**
     - Empty tomb tradition is early (pre-Pauline)
     - Historical certainty is difficult
     - Multiple explanations possible
3. **Identify Consensus**
   - All agree: Empty tomb tradition is early
   - All agree: Gospel accounts differ in details
4. **Map Tensions**
   - Apologetic: Differences are complementary
   - Skeptical: Differences suggest legend development
5. **Meta-Analysis**
   - Empty tomb tradition is early and widespread
   - Historical certainty depends on prior assumptions
   - Evidence is strong but not conclusive
6. **Return** - Tabbed UI with all 3 views + synthesis

---

## Integration Points

### Frontend (Next.js)
- **Chat Interface** - `/chat` route uses RAG workflow
- **Research Page** - `/research` uses detective mode with CoT
- **Discoveries** - `/discoveries` uses insight detection
- **Settings** - `/settings` configures model preferences

### Backend (FastAPI)
- **AI Router** - `theo/services/api/app/ai/router.py`
  - `/ai/chat` - Simple RAG
  - `/ai/research` - Detective mode with reasoning
  - `/ai/critique` - Meta-cognitive review
  - `/ai/perspectives` - Multi-perspective synthesis

### Database (PostgreSQL + pgvector)
- **Documents** - Source material with embeddings
- **Passages** - Chunked text with OSIS references
- **Agent Trails** - Research session logs
- **Reasoning Traces** - Chain-of-thought steps
- **Insights** - Novel connections discovered

---

## Testing & Evaluation

### Unit Tests
```bash
# Test reasoning modules
pytest tests/api/ai/test_reasoning_modules.py -v

# Test RAG workflow
pytest tests/api/ai/test_rag_workflow.py -v

# Test guardrails
pytest tests/api/ai/test_guardrails.py -v
```

### Evaluation Metrics

**Reasoning Quality:**
- Logical coherence: % of reasoning chains free of fallacies
- Evidence grounding: % of claims backed by citations
- Perspective balance: Distribution across skeptical/apologetic/neutral

**User Experience:**
- Time to insight: How quickly users find "aha!" moments
- Reasoning clarity: User ratings of trace understandability
- Trust signals: % of users who verify citations

**Safety:**
- Guardrail pass rate: % of generations passing validation
- Fallacy detection recall: % of planted fallacies caught
- Citation accuracy: % of citations that exist in corpus

---

## Future Enhancements

### Phase 1: Cognitive Gate v0 (Active)
- Harden prompt admission control, score calculations, and overrides.
- Replace legacy evaluator in Prompt-Observe-Update loop with gate-managed flow.
- Capture telemetry for gate outcomes and decision latencies.

### Phase 2: TMS & Debate Foundations (Planned)
- Launch Thought Management System (TMS) v0 for branching and archival.
- Persist debate rounds linked to hypotheses with guardrails and scoring rubrics.
- Provide admin tooling to replay sessions and inspect debate outcomes.

### Phase 3: Meta-Prompt Governance (Future)
- Deliver Meta-Prompt picker with presets (Exploratory, Apologetic, Critical, Synthesis).
- Instrument preset performance metrics and collect researcher feedback.
- Expand visualization layers for hypothesis evolution and contention heatmaps.

---

## Related Documentation

- **[AGENT_THINKING_ENHANCEMENT.md](AGENT_THINKING_ENHANCEMENT.md)** - Full design doc for reasoning framework
- **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** - Step-by-step implementation guide
- **[theoria_instruction_prompt.md](theoria_instruction_prompt.md)** - Master TRO instruction prompt
- **[AGENT_CONFINEMENT.md](AGENT_CONFINEMENT.md)** - Security framework for AI agents
- **[DISCOVERY_FEATURE.md](DISCOVERY_FEATURE.md)** - Auto-discovery engine design
- **[mcp_integration_guide.md](mcp_integration_guide.md)** - Model Context Protocol integration

---

## Quick Reference

### Import Paths
```python
# RAG
from theo.infrastructure.api.app.ai.rag.prompts import PromptContext, scrub_adversarial_language
from theo.infrastructure.api.app.ai.rag.guardrails import validate_answer
from theo.infrastructure.api.app.ai.rag.workflow import GuardedAnswerPipeline

# Reasoning
from theo.infrastructure.api.app.ai.reasoning.chain_of_thought import build_cot_prompt
from theo.infrastructure.api.app.ai.reasoning.fallacies import detect_fallacies
from theo.infrastructure.api.app.ai.reasoning.hypotheses import generate_hypotheses
from theo.infrastructure.api.app.ai.reasoning.insights import detect_insights
from theo.infrastructure.api.app.ai.reasoning.metacognition import critique_reasoning
from theo.infrastructure.api.app.ai.reasoning.perspectives import synthesize_perspectives

# Trails
from theo.infrastructure.api.app.ai.trails import create_trail, log_step
```

### API Endpoints
```
POST /api/ai/chat              # Simple RAG query
POST /api/ai/research          # Detective mode with CoT
POST /api/ai/critique          # Meta-cognitive review
POST /api/ai/perspectives      # Multi-perspective synthesis
GET  /api/ai/trails/:id        # Retrieve agent trail
POST /api/ai/trails/:id/replay # Replay trail with updates
```

### Environment Variables
```bash
# Model selection
THEORIA_DEFAULT_MODEL=gpt-5
THEORIA_FAST_MODEL=gpt-5-mini
THEORIA_DEEP_MODEL=o3-deep-research

# Safety
THEORIA_MAX_ITERATIONS=10
THEORIA_MAX_PASSAGES=50
THEORIA_ENABLE_GUARDRAILS=true

# Observability
THEORIA_LOG_TRAILS=true
THEORIA_LOG_REASONING=true
```

---

**Document Status:** v1.0  
**Last Updated:** 2025-01-15  
**Maintainer:** Theoria Development Team
