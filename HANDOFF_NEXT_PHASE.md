# Theoria - Next Phase Development Plan

> **Status:** Ready for implementation  
> **Last Updated:** 2025-01-15  
> **Estimated Timeline:** 4-6 weeks

---

## Executive Summary

Theoria has a solid foundation. Next phase: **complete discovery engine**, **expose agent reasoning**, **personalized dashboard**, and **citation export**.

### Current State ✅
- ✅ Frontend UI complete
- ✅ RAG pipeline working
- ✅ Reasoning framework implemented (not exposed)
- ✅ Discovery backend (pattern detection only)
- ✅ Background scheduler (just added)
- ✅ Comprehensive documentation

### What's Next 🎯
1. Complete Discovery Engine (5 missing types)
2. Expose Agent Reasoning in UI
3. Personalized Dashboard
4. Citation Manager

---

## Phase 1: Complete Discovery Engine (Week 1-2)

### 1.1 Contradiction Detection ⭐ HIGH PRIORITY
**Why:** High user value, leverages existing contradiction seeds

**Files to create:**
- `theo/domain/discoveries/contradiction_engine.py`
- `tests/domain/discoveries/test_contradiction_engine.py`

**Key implementation:**
- Use pre-trained NLI model (microsoft/deberta-v3-base-mnli)
- Compare document pairs for contradictions
- Link to existing contradiction seeds
- Confidence scores 0.6-0.95

### 1.2 Gap Analysis ⭐ HIGH PRIORITY
**Why:** Helps users discover missing topics

**Files to create:**
- `theo/domain/discoveries/gap_engine.py`
- `data/seeds/theological_topics.yaml`
- `tests/domain/discoveries/test_gap_engine.py`

**Key implementation:**
- Use BERTopic for topic modeling
- Compare against reference topics (Christology, Soteriology, etc.)
- Suggest searches to fill gaps

### 1.3 Connection Detection
**Why:** Builds on existing cross-reference data

**Files to create:**
- `theo/domain/discoveries/connection_engine.py`

**Key implementation:**
- Build graph from shared verse_ids
- Find bridge documents
- Calculate connection strength (Jaccard similarity)

### 1.4 Trend Detection
**Why:** Shows topic evolution over time

**Files to create:**
- `theo/domain/discoveries/trend_engine.py`

**Key implementation:**
- Compare current vs. historical snapshots
- Calculate topic frequency changes
- Identify emerging/declining topics

### 1.5 Anomaly Detection
**Why:** Find outlier documents

**Files to create:**
- `theo/domain/discoveries/anomaly_engine.py`

**Key implementation:**
- Use sklearn IsolationForest
- Identify outliers in embeddings
- Explain why anomalous

### Integration
Update `DiscoveryService.refresh_user_discoveries()` to run all engines.

---

## Phase 2: Expose Agent Reasoning (Week 3)

### 2.1 Reasoning Mode Toggle ⭐ HIGH PRIORITY
**Files to modify:**
- `theo/services/web/app/chat/page.tsx`
- `theo/services/api/app/ai/router.py`

**Add modes:**
- 🔍 Detective (step-by-step)
- 🤔 Critic (challenge assumptions)
- 🛡️ Apologist (harmonize)
- 📊 Synthesizer (survey all views)

### 2.2 Display Reasoning Trace
**Files to create:**
- `theo/services/web/components/ReasoningTrace.tsx`

**Features:**
- Expandable/collapsible
- Step-by-step display
- Confidence bars

### 2.3 Fallacy Warnings
**Files to create:**
- `theo/services/web/components/FallacyWarnings.tsx`

**Features:**
- Highlight high severity
- Show suggestions
- Educational tooltips

### 2.4 Hypothesis Dashboard
**Files to create:**
- `theo/services/web/app/research/hypotheses/page.tsx`

**Features:**
- Card view with confidence bars
- Supporting/contradicting evidence counts
- "Test Hypothesis" button

---

## Phase 3: Personalized Dashboard (Week 4)

### Implementation
**Files to modify:**
- `theo/services/web/app/page.tsx` (replace landing)

**Files to create:**
- `theo/services/api/app/routes/dashboard.py`

**Sections:**
1. Quick stats (documents, discoveries, queries, insights)
2. Recent activity timeline
3. Latest discoveries (top 6)
4. Quick actions (Upload, Chat, Browse, Search)
5. Bookmarked research

---

## Phase 4: Citation Manager (Week 5-6)

### 4.1 Citation Export ⭐ HIGH PRIORITY
**Files to create:**
- `theo/services/api/app/export/citations.py`
- `theo/services/web/components/CitationExport.tsx`

**Formats:**
- APA 7th Edition
- Chicago 17th Edition
- SBL 2nd Edition
- BibTeX

### 4.2 Bibliography Builder
**Files to create:**
- `theo/services/web/app/bibliography/page.tsx`

**Features:**
- Document selector
- Live preview
- Copy/download/email

### 4.3 Zotero Integration (Optional)
**Files to create:**
- `theo/services/api/app/export/zotero.py`

**Features:**
- API key configuration
- One-click export
- Batch support

---

## Testing Strategy

### Unit Tests
```bash
pytest tests/domain/discoveries/ -v
pytest tests/api/ai/test_reasoning_modules.py -v
pytest tests/api/export/test_citations.py -v
```

### Integration Tests
```bash
pytest tests/api/test_discovery_integration.py -v
pytest tests/api/test_reasoning_integration.py -v
pytest tests/api/test_dashboard.py -v
```

### Manual Testing
- [ ] Upload document → discoveries appear
- [ ] Chat in detective mode → reasoning shows
- [ ] Dashboard loads with stats
- [ ] Export citations works

---

## Deployment Checklist

1. Install dependencies: `pip install -r requirements.txt`
2. Run migrations
3. Restart: `.\start-theoria.ps1`
4. Verify scheduler: Check logs for "Discovery scheduler started"
5. Smoke test: Upload, chat, check dashboard

---

## Success Metrics

**Phase 1:** All 6 discovery types working, 10+ discoveries per user  
**Phase 2:** 30%+ use reasoning modes, 80%+ find helpful  
**Phase 3:** 80%+ sessions start from dashboard  
**Phase 4:** 40%+ export citations, 90%+ find useful  

---

## Risk Mitigation

**NLI too slow?** Use smaller model, cache results  
**BERTopic fails?** Require 20+ documents minimum  
**Too many discoveries?** Smart filtering, top 5 view  
**Users confused?** Add tooltips, examples, onboarding  

---

## Quick Reference

### Key Files Modified
- `requirements.txt` - Added apscheduler
- `theo/services/api/app/main.py` - Added scheduler lifecycle
- `theo/services/api/app/workers/discovery_scheduler.py` - New scheduler

### Key Documentation
- `docs/AGENT_AND_PROMPTING_GUIDE.md` - Agent architecture
- `docs/DISCOVERY_SCHEDULER.md` - Scheduler details
- `docs/DISCOVERY_FEATURE.md` - Discovery spec
- `docs/IMPLEMENTATION_GUIDE.md` - Reasoning framework

### Next Session Start Here
1. Review this handoff
2. Pick Phase 1.1 (Contradiction Detection)
3. Create `theo/domain/discoveries/contradiction_engine.py`
4. Implement NLI-based detection
5. Test and integrate

---

**Ready to start Phase 1!** 🚀
