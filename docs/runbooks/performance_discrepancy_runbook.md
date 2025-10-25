# Performance Discrepancy Runbook

Use this playbook when Lighthouse, rag_eval, or production telemetry diverge from expectations. The goal is to capture evidence quickly, coordinate mitigations, and align on next steps before customer impact grows.

## 1. Log the discrepancy
1. Create an incident ticket in Jira using the "Performance Regression" template.
2. Record the triggering metrics:
   - Lighthouse deltas (Performance score, LCP, CLS, TBT, Speed Index).
   - rag_eval before/after metrics and failing query IDs.
   - Grafana panel URLs from [Web Vitals Overview](https://grafana.theo.internal/d/web-vitals/core-web-vitals-overview), [RAG Retrieval Quality](https://grafana.theo.internal/d/rag-quality/rag-retrieval-efficacy), or [Edge Latency & Throughput](https://grafana.theo.internal/d/edge-latency/api-latency-distribution).
3. Document hypothesised root causes, current feature flag states, and the owning squad for each.
4. Attach recent deploy notes and the relevant `perf_metrics/*.json` artefacts from CI.

## 2. Notify stakeholders
- Page the on-call engineer via PagerDuty (service: `theo-engine-web`).
- Alert the Product Manager and Tech Lead in `#theo-perf-alerts` with a link to the Jira ticket.
- DM DevOps on-call if infrastructure support or feature flag toggles are required.

## 3. Coordinate load testing (if necessary)
1. If the regression coincides with backend/resource changes, schedule a load test slot with DevOps via `#devops-requests`.
2. Share target scenarios, expected concurrency, and data refresh requirements at least 2 hours in advance.
3. Run `scripts/perf/collect_rag_eval_metrics.py` after the load test to capture post-test retrieval metrics.
4. Post load test findings in the Jira ticket, noting whether results justify rollback, mitigation, or acceptance.

## 4. Mitigation and rollback decision tree
- **Fast fix available (<2h):** implement patch, rerun CI (Lighthouse + rag_eval), and monitor Grafana dashboards for confirmation.
- **Requires infrastructure changes:** align with DevOps on rollout plan; consider canary deployments with enhanced logging.
- **No immediate fix:** evaluate feature flag rollbacks or traffic shaping. Document risk acceptance if leaving the change live.

## 5. Post-incident documentation
1. Summarise the timeline, root cause, and remediation in the Jira ticket.
2. Update `docs/operations/performance.md` with new lessons or links if observability coverage changes.
3. File follow-up tasks for tech debt (e.g., missing baselines, flaky dashboards).
4. Close the ticket only after confirming metrics are back within tolerance for two consecutive reporting windows.

Maintaining tight feedback loops between engineering, QA, and DevOps keeps regressions rare and quickly mitigated.
