# Performance Monitoring Policy

This guide outlines how the Theoria team evaluates web performance in CI and how those lab runs relate to production data. Use it to interpret Lighthouse reports, understand why the numbers differ from Core Web Vitals collected in the field, and know when to open follow-up issues.

## Lab (Lighthouse) versus Field (RUM) data

Theoria's CI pipeline runs Lighthouse against controlled builds of the web UI. These synthetic measurements are:

- **Deterministic hardware/network** – Each run uses a standardized CPU throttle, network shaping, and cold cache to keep comparisons fair across commits.
- **Isolated test pages** – We evaluate key flows (landing page, authenticated dashboard, document reader) without background tabs or user interaction noise.
- **Repeatable** – Results are reproducible across branches and pull requests because the environment is scripted.

Real-user monitoring (RUM) data, gathered from production analytics, differs in several ways:

- **Device diversity** – Field data includes low-end Android phones, iOS tablets, and desktop hardware with widely varying capabilities.
- **Network variance** – Users hit the site on LTE, 3G, and corporate Wi-Fi. Packet loss and latency add noise not seen in CI.
- **Warm caches and service workers** – Returning visitors often benefit from cached assets and preloaded data, improving some metrics while hurting others if caches become stale.
- **Sample availability** – Core Web Vitals (CWV) thresholds depend on Chrome UX Report sampling. Low-traffic views may have sparse data that lags current releases.

Both views are necessary: Lighthouse protects regressions before merge, while RUM validates that optimizations benefit real traffic.

## Metrics we track

We currently monitor the following metrics in CI and production dashboards:

| Metric | Description | Target (lab) | Target (field) |
| --- | --- | --- | --- |
| Largest Contentful Paint (LCP) | Time until the main content is visible | ≤ 2.2 s | ≤ 2.5 s (75th percentile) |
| Cumulative Layout Shift (CLS) | Visual stability score | ≤ 0.08 | ≤ 0.10 |
| Interaction to Next Paint (INP) | Interaction responsiveness | ≤ 200 ms | ≤ 200 ms |
| Total Blocking Time (TBT) | Amount of main-thread blocking (lab only) | ≤ 150 ms | n/a |
| Speed Index | Visual progress of page load | ≤ 3.5 s | contextual |

TBT is a Lighthouse-only proxy for responsiveness, while INP is the corresponding Core Web Vital in the field.

## CI automation and baselines

GitHub Actions runs Lighthouse via [`lighthouserc.json`](../lighthouserc.json) on every PR, scheduled audit, and deployment to
`main`/`develop`. The workflow enforces the lab targets above with LHCI assertions:

- Performance score ≥ 0.90
- LCP ≤ 2.2 s
- CLS ≤ 0.08
- TBT ≤ 150 ms
- Speed Index ≤ 3.5 s

When `.lighthouseci/baseline/manifest.json` is present, the job writes a Markdown summary comparing the stored baseline against
the latest run. Review the job summary on your PR for per-URL deltas and copy the key numbers into the pull request template.
If a regression appears, record hypotheses (cache churn, flag flips, backend latency, etc.) and the mitigation owner in the PR
description so the team can follow up after merge.

To update the baseline after improvements land:

1. Check out `main` and run `npx @lhci/cli autorun` locally or re-run the CI job with a `main` ref.
2. Copy the generated `.lighthouseci/manifest.json` to `.lighthouseci/baseline/manifest.json` and commit it with the change log.
3. Reference the new baseline in the PR summary so reviewers understand the context for future comparisons.

## Interpreting lab reports

When you open a Lighthouse report generated in CI:

1. **Confirm the scenario** – The report URL indicates the page under test. Check that the view aligns with your change.
2. **Compare against the previous baseline** – We store the last passing metrics in the observability dashboard. Differences >10% should be explained in the PR description.
3. **Inspect audits driving regressions** – Expand the "Opportunities" and "Diagnostics" sections. Items like unused JavaScript or long tasks often map directly to the diff.
4. **Validate filmstrip and trace** – Use the screenshots and performance trace to ensure the page renders as expected and that no API call spikes latency.

## Interpreting production analytics

Field dashboards aggregate Core Web Vitals from CrUX, Web Vitals JS, and server logs:

- **Look at percentiles, not averages** – CWV uses the 75th percentile as the "good" threshold. Focus on that slice when comparing to lab data.
- **Segment by device class** – Desktop may exceed targets while mobile lags. Prioritize mobile regressions unless a desktop-only change landed.
- **Account for release cadence** – CrUX data is delayed ~28 days. If CI shows improvement but field data is stale, annotate the report instead of reverting.
- **Check cache hit ratios** – CDN or service-worker churn can tank field metrics even when Lighthouse is green.

## Observability dashboards

Keep these Grafana dashboards handy when triaging changes:

- [Web Vitals Overview](https://grafana.theo.internal/d/web-vitals/core-web-vitals-overview) – LCP/CLS/INP trends for landing page, dashboard, and reader broken down by device class.
- [RAG Retrieval Quality](https://grafana.theo.internal/d/rag-quality/rag-retrieval-efficacy) – Faithfulness, relevance, and fallback rate from nightly rag_eval comparison exports.
- [Edge Latency & Throughput](https://grafana.theo.internal/d/edge-latency/api-latency-distribution) – CDN cache hit ratios, p95 response time, and concurrent request saturation for API pods.

After deployment, confirm the expected trend direction in at least one of the dashboards above and link the panel snapshot in your release notes or PR.

## Common sources of discrepancies

| Cause | Effect | Mitigation |
| --- | --- | --- |
| Device CPU variance | Slower field INP/LCP than lab | Profile on a mid-tier Android in BrowserStack before shipping |
| Network instability | Field LCP spikes despite solid lab runs | Audit critical requests for cache headers and parallelization |
| Personalized content | Lab runs miss hydrated widgets that render slowly for real users | Add representative fixtures or auth flows to Lighthouse scenarios |
| Sampling noise | Field dashboards flip status with low traffic | Correlate with internal analytics and wait for more data |
| Aggressive caching | Field CLS improves while lab shows regressions | Verify cache invalidation to avoid stale UI |

## Thresholds that trigger follow-up

Open a tracking issue (or block the PR) when any of the following occur:

- **LCP exceeds 2.2 s in lab or 2.5 s (75th percentile) in field data** for two consecutive reporting windows.
- **CLS exceeds 0.08 in lab or 0.10 in field** for any key page.
- **INP (field) or TBT (lab) exceed targets by more than 25%** and the regression traces back to the current change.
- **Speed Index or other Lighthouse scores drop below 85** when the change touches critical rendering paths.
- **CI trendline deviates by >10%** for two runs even if thresholds remain technically within "good" ranges.

Document the affected route, suspected cause, and mitigation plan in the issue. If the regression originates from an external dependency (e.g., third-party script), note the owner and escalation path.

## Workflow checklist

- [ ] Review Lighthouse output on your PR and note any metric changes in the summary.
- [ ] Run `python -m theo.services.cli.rag_eval` and include before/after retrieval metrics when the change touches the reranker or intent tagger.
- [ ] Cross-check the observability dashboard after deployment to ensure field metrics track the expected direction.
- [ ] Log any discrepancies with hypotheses (cache warm-up, CDN purge timing, feature flags) in the release notes.
- [ ] Coordinate with DevOps for load tests when performance work ships alongside infrastructure changes.

The CI summary reiterates the hypotheses and load-test reminders to keep the team aligned whenever thresholds are close to
failing. Use it as a prompt to document unknowns immediately instead of waiting until post-merge triage.

Keeping both lab and field metrics healthy ensures Theoria delivers responsive study experiences across devices and networks.
