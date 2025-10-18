# Roadmap

> **Source of truth:** `HANDOFF_NEXT_PHASE.md` (last updated 2025-01-15)

This document summarizes the active roadmap derived from the handoff plan. Use it as a quick reference; consult `HANDOFF_NEXT_PHASE.md` for full implementation details and task breakdowns.

## Current Status

- **Discovery Engine**
  - Pattern detection 
  - Contradiction detection (DeBERTa-based engine completed January 2025)
  - Gap analysis Pending (BERTopic integration)
  - Connection, trend, anomaly detection Pending
  - Background scheduler (APScheduler refresh every 30 minutes)
- **Agent Reasoning UI** Not yet exposed (framework exists)
- **Personalized Dashboard** Planned
- **Citation Manager** Zotero integration shipped; broader manager roadmap tracked in Phase 4

## Phase 1 – Complete Discovery Engine (Weeks 1–2)

- **1.2 Gap Analysis (High Priority)**
  - Implement `theo/domain/discoveries/gap_engine.py`
  - Seed reference topics in `data/seeds/theological_topics.yaml`
  - Integrate BERTopic, add tests under `tests/domain/discoveries/`
- **1.3 Connection Detection**
  - Graph-based relationships via shared verses
  - Introduce `connection_engine.py` and supporting tests
- **1.4 Trend Detection**
  - Time-series analysis across corpus snapshots
  - Surface emerging and declining topics
- **1.5 Anomaly Detection**
  - IsolationForest-based outlier surfacing
  - Explain deviation using metadata and verse usage

## Phase 2 – Expose Agent Reasoning (Week 3)

- Add reasoning mode toggle in `theo/services/web/app/chat/page.tsx`
- Update API routing in `theo/services/api/app/ai/router.py`
- Render reasoning traces and fallacy warnings in new components under `theo/services/web/components/`
- Ship hypothesis dashboard at `/research/hypotheses`

## Phase 3 – Personalized Dashboard (Week 4)

- Replace landing page with personalized overview
- Create API route `theo/services/api/app/routes/dashboard.py`
- Surface quick stats, recent activity, discoveries, and bookmarks

## Phase 4 – Citation Manager (Weeks 5–6)

- Expand citation export formats (APA, Chicago, SBL, BibTeX)
- Enhance `/bibliography` builder and related API endpoints
- Continue polishing Zotero integration (`theo/services/api/app/export/zotero.py`)

## Maintenance Notes

- Keep this summary aligned with `HANDOFF_NEXT_PHASE.md` after each milestone.
- Update `docs/DISCOVERY_FEATURE.md` as new engines ship to reflect backend progress.
