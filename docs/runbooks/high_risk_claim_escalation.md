# High-Risk Claim Escalation Runbook

## Purpose
This runbook standardizes the human review workflow for unsupported or high-risk claims surfaced by the Audit subsystem. It ensures compliance stakeholders are alerted promptly and have the context needed to decide on final publication.

## Trigger Conditions
- Any claim labeled `REFUTED` or `NEI` with `confidence < 0.6`.
- Claims involving regulated medical, legal, or safety-critical guidance regardless of score.
- Automated policy checks that flag jurisdiction-specific compliance requirements (see compliance policy matrix).
- Manual escalation by moderators or subject-matter experts.

## Roles and Responsibilities
- **On-Call Compliance Analyst (Level 1)**: triages escalations within SLA, validates evidence, and determines if immediate remediation is required.
- **Domain Expert Reviewer (Level 2)**: provides subject-matter validation for complex neuroscience or regulatory claims when Level 1 cannot resolve.
- **Compliance Lead (Level 3)**: final decision-maker for disputes, approves public release, and interfaces with legal if necessary.
- **Audit Operations Engineer**: maintains tooling, monitors queues, and ensures the reporting layer reflects latest statuses.

## Tooling
- **Audit Console**: primary interface showing Claim Cards, evidence, and status history.
- **Compliance Case Tracker** (Jira project `COMP-ESC`): used for documenting human decisions and linking to remediation work.
- **Notification Channels**: Slack channel `#compliance-alerts` and email alias `compliance-oncall@theoria.ai`.
- **Reporting Layer**: dashboards described in `docs/audit_mode_spec.md` §§7–8 for visibility into queue metrics and SLA adherence.

## Workflow
1. **Automated Intake**
   - Audit subsystem pushes flagged claims into the Escalation Queue.
   - Reporting layer generates a ticket in `COMP-ESC` with metadata (claim ID, answer ID, risk flags, evidence URLs).
2. **Level 1 Review**
   - On-call analyst acknowledges within 30 minutes.
   - Validates evidence and either clears the claim (documenting rationale) or escalates to Level 2.
3. **Level 2 Review**
   - Domain expert responds within 4 business hours.
   - Provides authoritative confirmation/refutation and suggests remediation actions.
4. **Level 3 Arbitration (if needed)**
   - Compliance Lead renders decision within 1 business day.
   - Coordinates with legal and product stakeholders for sensitive outcomes.
5. **Resolution & Feedback**
   - Audit Operations Engineer updates Claim Card status and closes the ticket.
   - Lessons learned captured in weekly compliance review meeting.

## Communication Cadence
- Daily stand-up between Audit Ops and Compliance Analysts to review outstanding tickets.
- Weekly compliance review notes stored in `docs/runbooks/compliance_review_notes/<YYYY-MM-DD>.md` (create if absent).

## SLA Monitoring
- Reporting dashboards display mean/95th percentile response times for each level.
- Alerts trigger if SLA breach is imminent (Level 1 >25 minutes, Level 2 >3.5 hours, Level 3 >20 hours).

## Post-Incident
- For incidents classified Severity 1 or legal exposure, run a postmortem within 3 business days and attach findings to the corresponding `COMP-ESC` ticket.
