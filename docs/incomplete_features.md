# Incomplete Logic and Features

This document tracks dashboard areas that still need follow-up work after the October 2025 production rollout.

## Dashboard quick statistics

- **File:** `theo/services/web/app/dashboard/components/QuickStats.tsx`
- **Status:** Calls the FastAPI dashboard route for live metrics. Next steps include caching responses for signed-in users and surfacing trend deltas instead of single totals.

## Dashboard recent activity feed

- **File:** `theo/services/web/app/dashboard/components/RecentActivity.tsx`
- **Status:** Uses backend activity data. Follow-up items: add pagination/infinite-scroll, expose filters (documents vs. discoveries), and surface per-item context actions.

## Tracking Bugs
- Any dashboard-related bugs should be added to `docs/status/KnownBugs.md` with `Impacted Docs` pointing to this file.
