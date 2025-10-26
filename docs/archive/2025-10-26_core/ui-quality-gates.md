> **Archived on 2025-10-26**

# UI Quality Gates Reference

Theoria's web CI now enforces multiple automated guards. Use this page to interpret failures and plan remediation work.

## Inline Style & Component Size Gates

- **Source**: `npm run quality:gates`
- **Baseline**: `theo/services/web/config/ui-quality-baseline.json`
- **Failure Condition**: A file introduces more inline styles than its allowance or a component exceeds its permitted line count.
- **Remediation**:
  1. Run `npm run quality:gates` locally to confirm the failing files.
  2. Refactor inline styles to design system classes or break components into smaller units.
  3. After reducing counts, regenerate the baseline with `npm run quality:baseline` and commit the updated JSON.

## Accessibility Scans (axe)

- **Source**: `npm run test:a11y`
- **Coverage**: `/`, `/verse/John.3.16`, `/copilot`
- **Failure Condition**: Critical axe violations.
- **Artifacts**: Playwright report + `axe-*-critical.json` attachments for failing routes.
- **Remediation**: Reproduce locally with `npm run test:a11y`, inspect the JSON attachment, and apply semantic markup, ARIA fixes, or focus management updates as recommended by axe.

## Lighthouse Smoke Tests

- **Source**: `npm run test:lighthouse:smoke`
- **Configuration**: `lighthouserc.json` (performance ≥0.9, core web vitals budgets)
- **Artifacts**: `.lighthouseci/` manifest plus HTML reports (uploaded by CI).
- **Remediation**: Investigate regressions in bundle size, LCP, TBT, or CLS. Optimize rendering paths, lazy-load heavy modules, and check for blocking scripts.

## Vitest Coverage Gate

- **Source**: `npm run test:vitest`
- **Thresholds**: ≥80% for statements, branches, functions, and lines.
- **Remediation**: Add targeted unit tests. The coverage report lives at `theo/services/web/coverage/coverage-summary.json`.

## Dashboard

Run `npm run quality:dashboard` after major UI work to refresh `docs/dashboards/ui-quality-dashboard.md`. The report tracks inline style totals, component sizes, coverage, and bundle size trends for sprint demos.

## Workflow Checklist Before Merging

1. `npm run test:vitest`
2. `npm run quality:gates`
3. `npm run test:a11y`
4. `npm run test:lighthouse:smoke`
5. Update documentation or baseline artifacts if metrics improved.
