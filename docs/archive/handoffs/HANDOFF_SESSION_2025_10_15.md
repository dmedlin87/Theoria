# Theoria Development Session - October 15, 2025

## Executive Summary

This session implemented **background auto-discovery** and completed **Phase 1.1 (Contradiction Detection)** of the Discovery Engine. The system now automatically generates discoveries in the background using APScheduler and detects contradictions between documents using NLI.

---

## What Was Completed ✅

### 1. Background Discovery Scheduler
- **File:** `theo/infrastructure/api/app/workers/discovery_scheduler.py`
- **Integration:** `theo/infrastructure/api/app/main.py` (FastAPI lifecycle)
- **Docs:** `docs/DISCOVERY_SCHEDULER.md`
- **Dependency:** `apscheduler>=3.10,<4`

**Features:**
- Runs every 30 minutes
- Finds users with activity in last 7 days
- Refreshes discoveries automatically
- Graceful startup/shutdown

### 2. Contradiction Detection Engine
- **File:** `theo/domain/discoveries/contradiction_engine.py`
- **Tests:** `tests/domain/discoveries/test_contradiction_engine.py`
- **Docs:** `docs/CONTRADICTION_DETECTION.md`
- **Dependencies:** `transformers>=4.30,<5`, `torch>=2.0,<3`, `sentencepiece>=0.1.99,<0.2`

**Features:**
- NLI-based detection (DeBERTa-v3-base-mnli)
- Pairwise document comparison
- Contradiction type inference (theological/historical/textual/logical)
- Configurable thresholds

### 3. Comprehensive Documentation
- `HANDOFF_NEXT_PHASE.md` - 6-8 week Cognitive Scholar roadmap
- `docs/AGENT_AND_PROMPTING_GUIDE.md` - Agent architecture
- `docs/DISCOVERY_SCHEDULER.md` - Scheduler details
- `docs/CONTRADICTION_DETECTION.md` - Implementation guide

---

## Current System State

### Working ✅
- Frontend UI (complete)
- RAG pipeline with guardrails
- Pattern detection (DBSCAN clustering)
- Contradiction detection (NLI-based) ← NEW
- Background scheduler ← NEW
- Background tasks after uploads

### Missing ❌
- Gap Analysis (BERTopic)
- Connection Detection (graph-based)
- Trend Detection (time-series)
- Anomaly Detection (isolation forest)
- Agent reasoning UI (framework exists but not exposed)
- Personalized dashboard
- Citation manager

---

## Next Steps (Priority Order)

### Phase 1: Complete Discovery Engine (Week 1-2)

**1.3 Gap Analysis** (HIGH PRIORITY)
- File: `theo/domain/discoveries/gap_engine.py`
- Use BERTopic for topic modeling
- Compare against reference topics (Christology, Soteriology, etc.)
- Create: `data/seeds/theological_topics.yaml`
- Dependency: `bertopic>=0.15,<1`

**1.4 Connection Detection** (MEDIUM PRIORITY)
- File: `theo/domain/discoveries/connection_engine.py`
- Build graph from shared verse_ids
- Find bridge documents
- Dependency: `networkx>=3.0,<4`

**1.5 Trend Detection** (MEDIUM PRIORITY)
- File: `theo/domain/discoveries/trend_engine.py`
- Time-series analysis of topics
- Compare current vs historical snapshots
- Requires 3+ corpus snapshots

**1.6 Anomaly Detection** (LOW PRIORITY)
- File: `theo/domain/discoveries/anomaly_engine.py`
- Use sklearn IsolationForest
- Identify outliers in embeddings

### Phase 2: Expose Agent Reasoning (Week 3)

**2.1 Reasoning Mode Toggle**
- Modify: `theo/services/web/app/chat/page.tsx`
- Add modes: detective/critic/apologist/synthesizer
- Backend: `theo/infrastructure/api/app/ai/router.py`

**2.2 Display Reasoning Trace**
- Create: `theo/services/web/components/ReasoningTrace.tsx`
- Expandable step-by-step display

**2.3 Fallacy Warnings**
- Create: `theo/services/web/components/FallacyWarnings.tsx`

**2.4 Hypothesis Dashboard**
- Create: `theo/services/web/app/research/hypotheses/page.tsx`

### Phase 3: Personalized Dashboard (Week 4)

- Modify: `theo/services/web/app/page.tsx` (replace landing)
- Create: `theo/infrastructure/api/app/routes/dashboard.py`
- Sections: stats, activity, discoveries, quick actions

### Phase 4: Citation Manager (Week 5-6)

**4.1 Citation Export**
- Create: `theo/infrastructure/api/app/export/citations.py`
- Formats: APA, Chicago, SBL, BibTeX

**4.2 Bibliography Builder**
- Create: `theo/services/web/app/bibliography/page.tsx`

**4.3 Zotero Integration** (optional)
- Create: `theo/infrastructure/api/app/export/zotero.py`

---

## Deployment

### Install Dependencies
```bash
pip install -r requirements.txt
```

### First-Time Setup
```bash
# Download NLI model (~400MB, one-time)
python -c "from transformers import AutoModel; AutoModel.from_pretrained('microsoft/deberta-v3-base-mnli')"

# Start services
.\start-theoria.ps1
```

### Verify
```bash
# Check logs
tail -f logs/api.log | grep "Discovery scheduler"

# Should see: "Discovery scheduler started successfully"
```

---

## Key Files

### Created This Session
- `theo/infrastructure/api/app/workers/discovery_scheduler.py`
- `theo/domain/discoveries/contradiction_engine.py`
- `tests/domain/discoveries/test_contradiction_engine.py`
- `docs/DISCOVERY_SCHEDULER.md`
- `docs/CONTRADICTION_DETECTION.md`
- `docs/AGENT_AND_PROMPTING_GUIDE.md`
- `HANDOFF_NEXT_PHASE.md`

### Modified This Session
- `requirements.txt` (added apscheduler, transformers, torch, sentencepiece)
- `theo/infrastructure/api/app/main.py` (scheduler lifecycle)
- `theo/domain/discoveries/__init__.py` (export engine)
- `theo/infrastructure/api/app/discoveries/service.py` (integrate contradiction detection)
- `docs/INDEX.md` (added links)

### Important Existing Files
- `theo/domain/discoveries/engine.py` (pattern detection)
- `theo/infrastructure/api/app/discoveries/service.py` (service layer)
- `theo/infrastructure/api/app/discoveries/tasks.py` (background tasks)
- `theo/infrastructure/api/app/routes/discoveries.py` (API endpoints)
- `theo/services/web/app/discoveries/page.tsx` (frontend)

---

## Testing

### Unit Tests
```bash
pytest tests/domain/discoveries/test_contradiction_engine.py -v
```

### Integration Tests
```bash
pytest tests/api/test_discovery_integration.py -v
```

### Manual Testing
1. Upload document → discoveries appear within 30s
2. Wait 30 minutes → periodic refresh runs
3. Check `/api/discoveries?type=contradiction`

---

## Configuration

```bash
# Discovery scheduler interval (default: 30 minutes)
export THEORIA_DISCOVERY_INTERVAL=30

# Disable periodic scheduler
export THEORIA_DISABLE_DISCOVERY_SCHEDULER=true

# NLI model configuration
export THEORIA_NLI_MODEL=microsoft/deberta-v3-base-mnli
export THEORIA_CONTRADICTION_THRESHOLD=0.7
export THEORIA_MIN_CONTRADICTION_CONFIDENCE=0.6
```

---

## Success Metrics

### Phase 1 (Discovery Engine)
- ✅ All 6 discovery types generating discoveries
- ✅ Average 10+ discoveries per user with 50+ documents
- ✅ Discovery generation < 30s for typical corpus
- ✅ User feedback: 70%+ find discoveries helpful

### Phase 2 (Agent Reasoning)
- ✅ 30%+ of chat queries use reasoning modes
- ✅ Reasoning traces viewed by 50%+ of users
- ✅ User feedback: 80%+ find reasoning helpful

### Phase 3 (Dashboard)
- ✅ 80%+ of sessions start from dashboard
- ✅ User feedback: 85%+ prefer dashboard

### Phase 4 (Citations)
- ✅ 40%+ of users export citations
- ✅ User feedback: 90%+ find export useful

---

**Status:** Phase 1.1 complete (2/6 discovery types working)  
**Next:** Phase 1.2 - Gap Analysis with BERTopic  
**Timeline:** 6-8 weeks to complete Cognitive Scholar phases
