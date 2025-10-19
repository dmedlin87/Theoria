# Roadmap

> **Source of truth:** `HANDOFF_NEXT_PHASE.md` (last updated 2025-01-15)

This document summarizes the active roadmap derived from the handoff plan. Use it as a quick reference; consult `HANDOFF_NEXT_PHASE.md` for full implementation details and task breakdowns.

## Current Status

- **Discovery Engine**
  - Pattern detection ✅
  - Contradiction detection ✅ (DeBERTa-based engine)
  - Gap analysis ✅ (BERTopic integration with theological topic seed data)
  - Connection, trend, anomaly detection ✅ (wired into `DiscoveryService.refresh_user_discoveries`)
  - Background scheduler ✅ (APScheduler refresh every 30 minutes)
- **Agent Reasoning UI** Reasoning trace, fallacy warnings, and the new timeline panel are live in chat workflows
- **Personalized Dashboard** Dashboard API (`dashboard.py`) and web components consume real metrics and activity data
- **Citation Manager** Bibliography builder and Zotero export available; multi-format exports tracked as follow-up work

## Phase 1 - Discovery Engine Enhancements (Completed Q1 2025)

- Delivered six discovery detectors (pattern, contradiction, gap, connection, trend, anomaly)
- Persist discoveries through `DiscoveryService.refresh_user_discoveries()` with scheduler coverage
- Seed data shipped in `data/seeds/theological_topics.yaml`
- Follow-up: continue tuning confidence thresholds and add analytics dashboards

## Phase 2 - Expose Agent Reasoning (In Progress)

- Reasoning timeline models and components live in chat workflow responses
- Fallacy warnings and reasoning traces render alongside chat output
- Active work: CS-002 (loop controls) and CS-003 (plan panel) to increase steerability
- Upcoming: hypothesis dashboard and research loop orchestration

## Phase 3 - Personalized Dashboard (Alpha Live)

- `theo/services/api/app/routes/dashboard.py` returns live metrics and activity feeds
- Quick stats, recent activity, and discoveries widgets backed by real data
- Next iterations: add personalization controls, bookmarks, and alerts

## Phase 4 - Citation Manager (Foundational Features Shipped)

- Bibliography builder UI and Zotero export operational
- Supports citation exports through `theo/services/api/app/export/zotero.py`
- Next up: add APA/Chicago/SBL/BibTeX formatters and batch export improvements

## Maintenance Notes

- Keep this summary aligned with `HANDOFF_NEXT_PHASE.md` after each milestone.
- Update `docs/DISCOVERY_FEATURE.md` as new engines ship to reflect backend progress.
