## Summary
- 

## Testing
- 

## Performance checklist
> Document how this change impacts performance guardrails. Delete rows that are not applicable.

- **Lighthouse** – Paste key score deltas from the GitHub Action summary (Performance, LCP, CLS, TBT, Speed Index) and link to the artifact. Note hypotheses for any regressions and mitigation owners.
- **Reranker evaluation** – Attach before/after metrics from `python -m theo.application.services.cli.rag_eval` when retrieval or ranking code changes.
- **Dashboards & load testing** – Confirm the relevant observability dashboard (Core Web Vitals, latency, etc.) and whether a coordinated load test with infrastructure is required.

## Performance evidence attachments
- [ ] Linked Lighthouse diff or screenshots for impacted flows.
- [ ] Uploaded rag_eval comparison artefacts (JSON + Markdown) when retrieval/ranking paths are touched.
