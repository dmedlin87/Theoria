-- Add reasoning scaffolding tables
-- Run date: 2025-01-12

-- Reasoning traces for chain-of-thought
CREATE TABLE IF NOT EXISTS reasoning_traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trail_id UUID REFERENCES agent_trails(id) ON DELETE CASCADE,
    step_index INT NOT NULL,
    reasoning_type TEXT NOT NULL CHECK (reasoning_type IN (
        'hypothesis', 'critique', 'synthesis', 'chain_of_thought', 'revision'
    )),
    content JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ix_reasoning_traces_trail ON reasoning_traces(trail_id);
CREATE INDEX ix_reasoning_traces_type ON reasoning_traces(reasoning_type);

-- Insights discovered during reasoning
CREATE TABLE IF NOT EXISTS insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trail_id UUID REFERENCES agent_trails(id) ON DELETE CASCADE,
    insight_type TEXT NOT NULL CHECK (insight_type IN (
        'cross_ref', 'pattern', 'synthesis', 'tension_resolution', 'novel_connection'
    )),
    description TEXT NOT NULL,
    passage_ids UUID[] DEFAULT ARRAY[]::UUID[],
    osis_refs TEXT[] DEFAULT ARRAY[]::TEXT[],
    novelty_score REAL CHECK (novelty_score >= 0 AND novelty_score <= 1),
    user_feedback TEXT,  -- user can rate insight quality
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ix_insights_trail ON insights(trail_id);
CREATE INDEX ix_insights_type ON insights(insight_type);
CREATE INDEX ix_insights_novelty ON insights(novelty_score DESC) WHERE novelty_score IS NOT NULL;

-- Hypotheses generated and tested
CREATE TABLE IF NOT EXISTS hypotheses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trail_id UUID REFERENCES agent_trails(id) ON DELETE CASCADE,
    claim TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    supporting_passage_ids UUID[] DEFAULT ARRAY[]::UUID[],
    contradicting_passage_ids UUID[] DEFAULT ARRAY[]::UUID[],
    perspective_scores JSONB DEFAULT '{}'::jsonb,  -- {"skeptical": 0.7, "apologetic": 0.3, ...}
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN (
        'active', 'confirmed', 'refuted', 'uncertain'
    )),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ix_hypotheses_trail ON hypotheses(trail_id);
CREATE INDEX ix_hypotheses_status ON hypotheses(status);
CREATE INDEX ix_hypotheses_confidence ON hypotheses(confidence DESC);

-- Fallacy warnings detected
CREATE TABLE IF NOT EXISTS fallacy_warnings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trail_id UUID REFERENCES agent_trails(id) ON DELETE CASCADE,
    step_id UUID REFERENCES agent_steps(id) ON DELETE CASCADE,
    fallacy_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
    description TEXT NOT NULL,
    matched_text TEXT,
    suggestion TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ix_fallacy_warnings_trail ON fallacy_warnings(trail_id);
CREATE INDEX ix_fallacy_warnings_severity ON fallacy_warnings(severity);
CREATE INDEX ix_fallacy_warnings_type ON fallacy_warnings(fallacy_type);

-- Critiques of reasoning quality
CREATE TABLE IF NOT EXISTS reasoning_critiques (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trail_id UUID REFERENCES agent_trails(id) ON DELETE CASCADE,
    reasoning_quality INT CHECK (reasoning_quality >= 0 AND reasoning_quality <= 100),
    weak_citation_ids UUID[] DEFAULT ARRAY[]::UUID[],
    bias_warnings TEXT[] DEFAULT ARRAY[]::TEXT[],
    alternative_interpretations TEXT[] DEFAULT ARRAY[]::TEXT[],
    recommendations TEXT[] DEFAULT ARRAY[]::TEXT[],
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ix_reasoning_critiques_trail ON reasoning_critiques(trail_id);
CREATE INDEX ix_reasoning_critiques_quality ON reasoning_critiques(reasoning_quality);

-- Comments
COMMENT ON TABLE reasoning_traces IS 'Chain-of-thought reasoning steps from AI agents';
COMMENT ON TABLE insights IS 'Novel insights and connections discovered during reasoning';
COMMENT ON TABLE hypotheses IS 'Theological hypotheses generated and tested by agents';
COMMENT ON TABLE fallacy_warnings IS 'Logical fallacies detected in reasoning';
COMMENT ON TABLE reasoning_critiques IS 'Self-critiques of reasoning quality';

COMMENT ON COLUMN reasoning_traces.reasoning_type IS 'Type of reasoning: hypothesis generation, critique, synthesis, etc.';
COMMENT ON COLUMN insights.novelty_score IS 'How novel this insight is (0=common, 1=very rare)';
COMMENT ON COLUMN hypotheses.confidence IS 'Confidence in hypothesis (0=refuted, 1=confirmed)';
COMMENT ON COLUMN hypotheses.perspective_scores IS 'Confidence breakdown by theological perspective';
COMMENT ON COLUMN fallacy_warnings.severity IS 'How serious the fallacy is (low/medium/high)';
COMMENT ON COLUMN reasoning_critiques.reasoning_quality IS 'Overall quality score 0-100';
