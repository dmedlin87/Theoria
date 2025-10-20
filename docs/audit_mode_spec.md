# Theoria Audit and Verification System Specification

> **Status:** Deferred concept. The workflow described in this document has not been implemented. The only production audit functionality today is basic request/response logging via `AuditLogWriter`. This specification is retained as future-looking design material and should not be interpreted as describing live capabilities.

## 1. Purpose and Context
Theoria currently relies on retrieval-augmented generation (RAG) to synthesize responses for domains that are rich in neuroscience and reasoning-heavy content. Because the product owners may not always have deep subject-matter expertise, they need an automated way to judge whether answers are faithful to trusted sources before presenting them to end users. This specification describes a multi-mode audit subsystem that adds layered verification, structured provenance logging, and human escalation paths without requiring a permanent human-in-the-loop.

## 2. High-Level Goals
- **Replace ad-hoc manual vetting** with an agentic workflow that self-checks answers before they reach users.
- **Expose actionable trust signals** (claim-level labels, confidence scores, provenance) so non-experts can decide when human review is required.
- **Maintain normal response speed** while providing an on-demand and automated audit trail for high-risk answers.
- **Support nightly batch verification** that surfaces problematic knowledge-base entries or stale citations.

## 3. Operating Modes
| Mode | Trigger | Behavior | Outputs |
| --- | --- | --- | --- |
| **Normal** | Default mode or user selection | Standard RAG answer generation using existing retrieval, answer drafting, and citation attachment. | Final answer with inline citations. |
| **Audit-Local** | Manual toggle or automatic trigger (e.g., domain risk level, user role) | Executes the verification loop using only indexed internal sources. Scores each claim for faithfulness and stores provenance. | Final answer, claim-level labels (SUPPORTED/REFUTED/NEI), confidence scores, structured Claim Cards. |
| **Audit-Web** | Escalation from Audit-Local due to low confidence, missing support, or conflicting evidence | Performs targeted web search against whitelisted domains, runs verification, and revises answer if needed. | Revised answer with external citations, Claim Cards noting external provenance, escalation log. |

## 4. System Components
### 4.1 Claim Extraction
- Segment each generated answer into atomic factual claims (numbers, named entities, causal statements).
- Use a deterministic prompt template that produces JSON `[{"claim_id": "c1", "text": "..."}, ...]`.

### 4.2 Verification Loop
1. **CoVe Self-Consistency**
   - Generate verification questions for each claim.
   - Re-answer using the retriever; compare with the drafted claim.
   - Produce a consistency score per claim.
2. **SelfCheck Sampling**
   - Sample `k` alternate answers using controlled temperature.
   - Flag claims that contradict or lack mention across samples.
3. **Evidence Retrieval**
   - Retrieve supporting passages from the knowledge base (and from the web when in Audit-Web mode).
   - Score relevance/faithfulness via embedding similarity and token overlap.
4. **RAGAS Scoring**
   - Compute faithfulness, answer relevance, and context precision/recall metrics.
   - Aggregate into `audit_score` ∈ [0,1].
5. **Claim Labeling**
   - Map evidence and scores to FEVER-style labels:
     - `SUPPORTED` when evidence aligns and score ≥ threshold.
     - `REFUTED` when evidence contradicts claim.
     - `NEI` when no evidence exists or confidence < threshold.

### 4.3 Escalation Logic
- Escalate to Audit-Web when any of the following are true:
  - Claim has `audit_score < audit_score_threshold` (see appendix).
  - No supporting passage retrieved locally.
  - SelfCheck disagreement ratio > `selfcheck_disagreement_threshold` (currently 0.40).
  - Source age exceeds freshness policy (e.g., >18 months for neuroscience claims).
- In Audit-Web mode, restrict searches to configured domains (PubMed, arXiv, ACL Anthology, etc.) and annotate Claim Cards with external provenance.

### 4.4 Provenance Logging
- Persist Claim Cards following a W3C PROV-inspired schema (see §6).
- Store linkage between answers, claims, evidence chunks, and verification methods.
- Support filtering and export (e.g., daily CSV/JSON bundles of low-confidence claims).

### 4.5 Nightly Batch Auditor
- Reprocess the day’s interactions focusing on claims labeled `REFUTED` or `NEI` with confidence <`low_confidence_threshold` (0.60).
- Re-run verification with refreshed retrieval indices and web checks.
- Produce a summary report (top failing KB entries, stale sources, recommended human review items).
- Optionally trigger re-indexing tasks or knowledge-base curation tickets.

## 5. Data Flow Overview
1. **Answer Drafting**: Standard RAG pipeline produces a draft answer with citations.
2. **Claim Extraction**: Draft is converted into atomic claims.
3. **Local Verification**: CoVe + SelfCheck + evidence retrieval produce metrics and labels.
4. **Escalation Decision**: Based on metrics, either finalize (Normal/Audit-Local) or escalate (Audit-Web).
5. **External Verification**: Conduct targeted web verification; update answer and labels.
6. **Storage**: Persist Claim Cards, audit metrics, and final answer in the audit store.
7. **Batch Processing**: Nightly job re-evaluates low-confidence claims and generates reports.

## 6. Claim Card Schema (JSON)
```json
{
  "claim_id": "c1",
  "answer_id": "a-2025-10-18-001",
  "text": "Long-term potentiation requires NMDA receptor activation.",
  "mode": "Audit-Local",
  "label": "SUPPORTED",
  "confidence": 0.87,
  "evidence": [
    {
      "source_type": "kb",
      "source_id": "kb_chunk_1345",
      "title": "Synaptic Plasticity Overview",
      "uri": "kb://synaptic_plasticity_overview",
      "snippet": "Long-term potentiation (LTP) is dependent on NMDA receptors...",
      "hash": "sha256:..."
    }
  ],
  "verification_methods": [
    "CoVe",
    "SelfCheckGPT",
    "RAGAS"
  ],
  "metrics": {
    "faithfulness": 0.86,
    "answer_relevance": 0.92,
    "context_precision": 0.78,
    "selfcheck_disagreement": 0.1
  },
  "timestamps": {
    "drafted_at": "2025-10-18T08:15:00Z",
    "verified_at": "2025-10-18T08:15:12Z"
  },
  "escalations": []
}
```

## 7. Integration Points
- **Retrieval Service**: Extend API to support claim-focused queries and freshness filters.
- **Generation Orchestrator**: Add mode toggle (Normal vs Audit-Local vs Audit-Web) and attach verification loop results to responses.
- **Audit Store**: Extend the existing PostgreSQL persistence layer with dedicated schemas/tables for Claim Cards and audit reports, leaning on JSONB columns for flexible metrics payloads while preserving relational joins for lineage, access control, and batch analytics.
- **Reporting Layer**: Dashboard widgets for trust scores, claim statuses, and nightly audit summaries.
- **External Search Connector**: Service wrapper for controlled web search with domain allow-listing and caching.

## 8. User Experience Considerations
- **UI Indicators**: Display per-claim badges (Supported, Refuted, Needs Evidence) with hover tooltips showing key metrics.
- **Mode Selection**: Provide toggle in admin console; allow per-user or per-conversation defaults.
- **Escalation Queue**: Dedicated view that lists claims requiring human follow-up, sorted by risk.
- **Export Functionality**: Allow exporting Claim Cards for external review (e.g., sending to a trusted agent for validation).

## 9. Security & Compliance
- Ensure external verification calls respect data residency policies.
- Hash or redact sensitive KB content when storing snippets.
- Maintain audit logs for regulatory compliance (timestamps, actors, decisions).

## 10. Implementation Roadmap
1. **Phase 0 – Foundations (1-2 weeks)**
   - Implement Claim Extraction service and Claim Card schema.
   - Integrate RAGAS scoring into current pipeline.
2. **Phase 1 – Audit-Local (2-3 weeks)**
   - Build verification loop with CoVe and SelfCheck.
   - Store Claim Cards and expose metrics in API/UI.
3. **Phase 2 – Audit-Web (2 weeks)**
   - Add escalation logic and external search connector.
   - Update UI to display external provenance.
4. **Phase 3 – Batch Auditor & Reporting (2 weeks)**
   - Implement nightly job, reporting dashboards, and export utilities.
5. **Phase 4 – Refinement & Automation (ongoing)**
   - Tune thresholds, add domain-specific rules, integrate model monitoring.

## 11. Escalation Process
### 11.1 Compliance Stakeholders & Review Gates
- **Audit Triage Analyst (ATA)** – First-line reviewer who validates data completeness and assigns severity.
- **Subject Matter Expert (SME)** – Domain-specialized reviewer (e.g., clinician, neuroscience researcher) who judges technical accuracy.
- **Compliance Officer (CO)** – Regulatory authority responsible for final approval and release decisions.
- **Audit Engineering Liaison (AEL)** – Engineering representative who implements remediation and ensures telemetry/reporting consistency.

These roles are sourced from the compliance stakeholder workshop (Oct 2025) and map directly to the human review checkpoints required for unsupported or high-risk claims. Each claim escalated from Audit-Web must pass ATA → SME → CO → AEL stages before closure.

### 11.2 Triggering Conditions
Escalation is mandatory when:
- A claim remains `REFUTED` or `NEI` after Audit-Web verification with `audit_score < 0.60`.
- The taxonomy labels a claim as `compliance_risk` (medical, legal, safety-critical guidance).
- Manual escalation is initiated from the dashboard queue by any compliance stakeholder.

### 11.3 Workflow Alignment with Reporting Layer (§7–§8)
1. **Queue Intake (ATA)** – Initiated from the reporting layer’s Escalation Queue (see §7–§8). ATA validates provenance in the Claim Card detail view, tags severity, and creates/links Jira ticket `AUD-<id>` for traceability. SLA: within 2 business hours of queue appearance.
2. **SME Review** – SME accesses the same Claim Card drill-down, reviews attached evidence, and records recommendations directly in the dashboard notes (rendered in the reporting layer widgets). SLA: within 1 business day of ATA completion.
3. **Compliance Approval** – CO verifies regulatory obligations, uses dashboard approval controls to set final disposition (Publish, Block, Retract), and updates the associated Jira ticket. SLA: within 1 business day of SME decision.
4. **Engineering Follow-up** – AEL implements remediation, updates Claim Card status via the audit store API, and attaches remediation evidence in Jira. SLA: within 2 business days of compliance approval. Reporting layer widgets reflect closed items and SLA adherence for auditability.

All SLA clocks and state transitions surface in the reporting layer dashboards, enabling compliance leadership to audit performance and export weekly summaries.

### 11.4 Tooling & Documentation
- Audit Dashboard (reporting layer §7–§8) for queue management, role hand-offs, and note capture.
- Jira project `AUD` for remediation tracking with SLA automation.
- Slack `#audit-escalations` for asynchronous coordination; PagerDuty `Audit Compliance` service for SLA breach alerts.
- Detailed operational steps live in `docs/runbooks/high_risk_claim_escalation.md`, which governs day-to-day execution and on-call coverage.

### 11.5 Post-Escalation Analytics
- Weekly compliance reports aggregate open/closed escalations, SLA breaches, and remediation themes. Generated from the audit store via the reporting layer export routines described in §7.
- Recurrent infractions originating from the same knowledge source trigger a retrospective led by the AEL within 5 business days.

### 11.6 Related Implementation Notes
- **Storage backend decision (resolved)**: Claim Cards and audit telemetry persist in PostgreSQL alongside existing Theo schemas. This ensures transactional writes across answers, claims, evidence slices, and escalation events while reusing SQLAlchemy infrastructure and BI exports (`run_sql_migrations.py`, Alembic migrations).
- **Document store evaluation**: MongoDB/Cosmos-style stores were rejected because they fragment provenance queries and weaken compliance controls that rely on relational constraints and retention policies.
- **Audit-Web latency budget (resolved 2025-10-18)**: Audit-Web escalation overhead is capped at ≤3.0 s p95 to keep total response time within 3.5 s while respecting UX guardrails (heavy operations <5 s, primary content visible by 2.5 s).
- **Audit-Web external API access (resolved 2025-10-21)**: External lookups target PubMed, arXiv, and ACL Anthology. PubMed uses service principal–scoped API keys (`THEO_AUDIT_PUBMED_API_KEY`), rotated every 90 days, injected via environment variables, and governed by `docs/security/secret-scanning.md` procedures.
- **Monitoring & observability for external connectors (resolved 2025-10-21)**: Outbound requests emit structured metrics via `theo.services.api.app.ai.audit_logging`; alerts trigger on PubMed quota depletion (<20% hourly) or 5xx rates >2% over 5 minutes, supplemented by nightly heartbeat probes.
- **Implementation follow-ups for `theo/services/api/app/ai/` connectors**: Extend `clients.py` with dedicated PubMed/Arxiv/AclAnthology clients, update `rag/retrieval.py` selection logic, wire configuration in `registry.py`, and add masked-auth tests under `theo/services/api/app/ai/tests/` with VCR fixtures.

## 12. Success Metrics
- ≥90% of audited claims labeled `SUPPORTED` without human intervention.
- ≤5% of audited claims escalated due to missing evidence after 30 days of operation.
- p95 audit latency increase ≤ 2s for Audit-Local mode.
- p95 audit latency increase ≤ 3s for Audit-Web mode with p95 total response time ≤ 3.5s.
- Nightly reports reduce knowledge-base correction backlog by ≥30% within the first quarter.

## 13. Appendix: Threshold Defaults
- `audit_score_threshold`: 0.80
- `selfcheck_disagreement_threshold`: 0.40
- `low_confidence_threshold`: 0.60
- Freshness policy: neuroscience sources ≤18 months old, general references ≤36 months.

