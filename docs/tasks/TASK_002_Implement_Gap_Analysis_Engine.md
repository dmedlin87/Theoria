# TASK 002: Implement Gap Analysis Engine (Cognitive Scholar Component)

**Priority**: ⭐⭐⭐ HIGH  
**Estimated Time**: 3-4 hours  
**Dependencies**: BERTopic (already in requirements.txt)  
**Status**: Ready to start  
**Cognitive Scholar Alignment**: Knowledge-Gap Generator (§2.3), Gap→Loop Plumbing (Appendix §A.6)

---

## 🎯 Objective

Implement Gap Analysis discovery engine using BERTopic to identify under-represented theological topics in user's corpus. This component feeds the Cognitive Scholar's Knowledge-Gap Generator, enabling autonomous curiosity-driven research loops.

---

## 📋 Key Files

### Create:
1. `theo/domain/discoveries/gap_engine.py` - Main engine implementation
2. `data/seeds/theological_topics.yaml` - Reference topic taxonomy
3. `tests/domain/discoveries/test_gap_engine.py` - Unit tests

### Modify:
1. `theo/services/api/app/discoveries/service.py` - Integrate gap engine
2. `theo/domain/discoveries/__init__.py` - Export GapDiscovery

---

## 🔧 Implementation Steps

1. **Create GapDiscoveryEngine class**
   - Uses BERTopic for topic modeling
   - Compares corpus topics vs reference taxonomy
   - Returns gaps with confidence scores

2. **Create theological topics YAML**
   - Reference topics: Christology, Soteriology, Pneumatology, etc.
   - Keywords for each topic domain

3. **Write unit tests**
   - Test with/without sufficient documents
   - Test confidence thresholding
   - Test max_gaps limiting

4. **Integrate into DiscoveryService**
   - Initialize gap_engine
   - Call detect() in refresh cycle
   - Persist gap discoveries

---

## ✅ Success Criteria

- [ ] GapDiscoveryEngine detects under-represented topics
- [ ] Returns GapDiscovery objects with metadata
- [ ] Unit tests pass (16+ tests recommended)
- [ ] Integrated into discovery refresh cycle
- [ ] Performance: <5 seconds for 100 documents

---

## 📚 References

- **Existing Gap Engine**: `theo/domain/discoveries/gap_engine.py` ✅
- **Integration Map**: `docs/tasks/COGNITIVE_SCHOLAR_INTEGRATION_MAP.md` 📊
- **Cognitive Scholar Spec**: `docs/tasks/theoria_feature_brainstorm_cognitive_scholar_v_1.md`
- Pattern Reference: `theo/domain/discoveries/engine.py` (PatternDiscoveryEngine)
- Service Integration: `theo/services/api/app/use_cases/refresh_discoveries.py`
- Testing Pattern: `tests/domain/discoveries/test_pattern_engine.py`

---

## 🧠 Cognitive Scholar Integration Notes

This gap detection engine will eventually feed into the Cognitive Scholar's autonomous research loops:

1. **Gap Detection** (this task) → identifies missing topics/evidence
2. **Falsifier Search Operator** (future) → generates targeted queries for gaps
3. **Retrieval Budgeter** (future) → executes searches within cost/time limits
4. **Hypothesis Updater** (future) → revises beliefs based on new evidence

The gap engine should return structured metadata suitable for query generation (e.g., missing topic keywords, suggested search terms, priority scores).

**Next Task**: TASK_003 (Query Optimization)
