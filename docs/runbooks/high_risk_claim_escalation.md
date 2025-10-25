# High-Risk Claim Escalation Runbook

> **Status:** Archived playbook. The automation, dashboards, and roles referenced below are not available in the current product. The live system only writes raw audit logs; this runbook is preserved for future implementation planning.

## Purpose
Provide a consistent escalation workflow for unsupported or high-risk claims emitted by the Theoria audit subsystem. This runbook aligns with the reporting layer defined in `docs/security/audit-mode-spec.md` §7–§8 and ensures regulatory compliance by prescribing human review checkpoints and documentation standards.

## Trigger Conditions
Escalate a claim when any of the following occur:
- Claim label `REFUTED` or `NEI` persists after Audit-Web verification.
- `audit_score` < 0.60 after Audit-Web re-run.
- Claim references regulated medical, legal, or safety-critical guidance flagged by taxonomy tag `compliance_risk`.
- Compliance stakeholder manually requests review via the dashboard escalation queue.

## Stakeholder Roles
- **Audit Triage Analyst (ATA)** – First-line reviewer. Owns initial screening and data completeness check.
- **Subject Matter Expert (SME)** – Domain expert (e.g., neuroscience researcher, clinician). Validates technical accuracy.
- **Compliance Officer (CO)** – Ensures regulatory obligations are met; final approval authority.
- **Audit Engineering Liaison (AEL)** – Provides tooling support, regenerates reports, and coordinates fixes in the RAG pipeline.

## Tooling
- **Audit Dashboard** (reporting layer in `docs/security/audit-mode-spec.md` §7–§8): Escalation queue, claim drill-down, and approval controls.
- **Claim Card Detail View**: Displays provenance, verification metrics, and evidence attachments.
- **Case Management Ticketing** (Jira project `AUD`): Tracks remediation tasks with SLA timers.
- **Notification Channels**: Slack channel `#audit-escalations` for asynchronous updates; PagerDuty service `Audit Compliance` for urgent breaches.

## Workflow & SLAs
1. **Queue Intake (ATA) – within 2 business hours**
   - Review claim metadata in the dashboard.
   - Confirm evidence completeness; request rerun if provenance is missing.
   - Classify severity (High, Medium, Low) based on risk taxonomy.
2. **SME Review – within 1 business day of intake**
   - Evaluate claim content against source materials.
   - Recommend outcome: Approve with edits, Reject claim, or Request additional evidence.
   - Document findings in the dashboard notes, attach external references if used.
3. **Compliance Approval (CO) – within 1 business day of SME decision**
   - Validate that SME recommendation satisfies regulatory requirements.
   - Decide final disposition (Publish, Block, or Retract associated answer).
   - Ensure Jira ticket reflects disposition and any mandated user notifications.
4. **Engineering Follow-up (AEL) – within 2 business days of compliance approval**
   - Implement required pipeline changes (KB updates, retrieval tuning, prompt adjustments).
   - Update Jira ticket with remediation evidence and close once validated.

## Exception Handling
- If SLA is at risk, responsible owner escalates via PagerDuty to ensure coverage.
- For repeated infractions of the same knowledge source, AEL schedules a retrospective within 5 business days.

## Documentation & Reporting
- Every escalation retains dashboard notes, attached evidence, and SLA timestamps.
- Weekly report summarizes open escalations, SLA breaches, and remediation outcomes; sent to compliance leadership.

