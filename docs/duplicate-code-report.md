# Duplicate Code Assessment

## Methodology
- Ran `npx jscpd --reporters json --output tmp/jscpd-report --min-tokens 50` from the repository root to scan for duplicate code blocks across the project.
- Parsed the resulting `tmp/jscpd-report/jscpd-report.json` to understand duplicate clusters, prioritizing the longest sequences of repeated lines.

## Key Statistics
- **Total duplicated lines:** 3,896 (out of 176,609 scanned lines, ~2.21% duplication).
- **Detected clone groups:** 293 across 1,193 source files.
- Duplicates span multiple languages and asset types, with concentrations in TypeScript/TSX, Python, CSS modules, and test fixtures.

## High-Impact Duplication Hotspots

### 1. Next.js API proxy routes (TypeScript)
Multiple API handlers mirror each other when forwarding requests to backend services. Example clusters include:
- `theo/services/web/app/api/ingest/url/route.ts` ↔ `theo/services/web/app/api/ingest/file, simple, export, analytics/.../route.ts` – repeated request forwarding, header plumbing, and error handling blocks.
- `theo/services/web/app/api/discoveries/[id]/route.ts`, `/view/route.ts`, and `/feedback/route.ts` – nearly identical fetch logic for different endpoints.

**Opportunity:** Extract a shared proxy helper that accepts the downstream path and optional payload preparation, reducing duplication of header forwarding, error responses, and response marshalling.

### 2. React hooks and components (TS/TSX)
Large swaths of UI logic are duplicated inside individual files or across related components:
- `useSearchFiltersState.ts` repeats complex reducer logic in multiple branches; `useSearchFilters.ts` duplicates the same helper flows.
- Chat workspace components (`ChatWorkspace.tsx`, `ChatWorkspace.refactored.tsx`, and transcript components) copy many sections of JSX and business logic.
- Upload forms (`FileUploadForm.tsx` ↔ `UrlIngestForm.tsx`) and research panels share nearly identical JSX/CSS blocks.

**Opportunity:** Break out shared hooks, reducers, and reusable child components, or centralize state management to avoid drift between copies.

### 3. CSS modules
Dashboard, research, and global theming CSS files contain repeated rule sets (e.g., `DiscoveryPreview.module.css` ↔ `RecentActivity.module.css`, `AppShell.module.css` internal duplication, and repeated theme blocks).

**Opportunity:** Consolidate recurring utility classes into shared CSS/SCSS modules or Tailwind-style tokens to improve maintainability.

### 4. Backend Python services
Back-end routes and services exhibit recurring control-flow patterns:
- API routes (`app/routes/export.py`, `routes/jobs.py`, `routes/verses.py`) reuse long handler segments for pagination and response formatting.
- Services such as `app/discoveries/service.py`, `app/notebooks/service.py`, and `app/retriever/*` repeat similar orchestration logic.
- Domain models (`app/models/research.py`) contain near-identical property/method definitions.

**Opportunity:** Factor repeated handler logic into base classes or shared utility functions, and consider declarative configuration for repeated route wiring.

### 5. Test suites
Test files under `theo/services/api/tests`, `tests/api`, and related directories heavily duplicate setup/teardown blocks and request fixtures.

**Opportunity:** Centralize shared fixtures and helper assertions (e.g., Pytest fixtures, factory functions) to decrease copy/paste across tests.

### 6. Scripts and documentation
- CLI and automation scripts (`scripts/launcher_helpers.py`, `scripts/eval_reranker.py`, `scripts/train_reranker.py`, etc.) replicate command-line parsing and status reporting.
- Historical markdown logs and temporary debug scripts are nearly identical across versions (`ingest_test_detail*.txt`, `tmp_debug*.py`).

**Opportunity:** Deduplicate scripts by introducing shared libraries or by deprecating archived duplicates; consider pruning obsolete documentation copies to cut noise.

## Suggested Next Steps
1. **Prioritize proxy route refactors** to minimize risk of inconsistent authentication or error messaging across ingestion/export endpoints.
2. **Audit duplicated React hook logic** to create composable primitives that the various UI surfaces can reuse.
3. **Create shared styling utilities** (e.g., design tokens or mixins) for repeated CSS blocks.
4. **Introduce backend helper abstractions** for repeated job/export workflows to simplify maintenance and improve testability.
5. **Invest in shared test fixtures** to reduce noise and prevent divergence when endpoints change.
6. **Sunset redundant scripts and documents** once their content is merged elsewhere, or generate them from a single source of truth.

Re-run the command above to regenerate `tmp/jscpd-report/jscpd-report.json` if you need to inspect specific clone groups in detail.
