# Adjacent User Needs & Pain Points

> **Last Updated:** 2025-10-31
> **Purpose:** Identify high-value adjacent problems for Theoria users that extend beyond the platform's current verse-anchored research workflows.

## Context

Theoria excels at deterministic retrieval, OSIS-normalized verse aggregation, and evidence-backed summarization. Pastors, academic researchers, and research assistants rely on the platform to keep theological analysis traceable and well-cited. As adoption grows, teams are asking Theoria to support the broader lifecycle of sermon preparation, comparative scholarship, and ministry coordination. This brief highlights unmet needs that repeatedly surface in interviews, support threads, and roadmap planning sessions but are not yet core product features.

## Adjacent Needs by Persona

| Persona | Current Usage Patterns | Emerging Pain Points | Opportunity Signals |
| --- | --- | --- | --- |
| **Lead Pastor / Teaching Team** | Weekly sermon prep, liturgical planning, reference exports for slides and handouts. | • Manual workflows to map retrieved passages onto sermon outlines and liturgical calendars.<br>• Limited sharing: exporting citations to collaborators requires out-of-band documents.<br>• No guardrails for pastoral care follow-up when passages surface sensitive topics. | • High willingness to pay for collaboration features tied to calendars.<br>• Repeated requests for templated sermon outlines with embedded citations.<br>• Ministry teams want prompts tuned for pastoral care scenarios. |
| **Academic Researcher** | Comparative doctrinal studies, cross-tradition source gathering, citation exports to Zotero. | • Fragmented cross-language support; manual translation of patristic / Latin sources.<br>• Desire for structured argument maps tying theses to verse evidence.<br>• Difficulty replaying complex search sessions when preparing peer reviews. | • Institutions requesting multi-user workspaces with audit logs.<br>• Willingness to share anonymized corpora if Theoria can return alignment metrics.<br>• Potential grants for digital humanities tooling that accelerate translation alignment. |
| **Research Assistant / Librarian** | Corpus ingestion, quality checks, metadata clean-up, supporting multiple leaders. | • Lacks task queueing to manage ingestion pipelines and QA sign-off.<br>• Struggles to signal content freshness (e.g., which sources need re-indexing after updates).<br>• Manual triage of ingestion failures across Slack/email. | • Teams adopt shadow spreadsheets to manage ingest tasks—opportunity to replace with native workflows.<br>• Libraries express interest in auto-generated audit trails for compliance.<br>• Desire for SLA-style dashboards summarizing ingestion success rates. |
| **Lay Leader / Small Group Facilitator** | Quick topical studies, home group curriculum preparation, volunteer coordination. | • Content surfaced is research-grade but lacks simplified teaching guides.<br>• Needs prompts tailored for discussion questions and contextual applications.<br>• Mobile experience for referencing notes in live sessions is underpowered. | • Growing inbound requests for "guided study" exports.<br>• High retention risk if materials stay too technical.<br>• Potential viral growth if small groups can co-create annotated guides. |

## Pain Point Narratives

1. **"Our sermon team uses Theoria to verify citations, but the outline lives in Notion."**<br>
   *Signal:* Export flows stop at citation lists, forcing pastors to manually rebuild outlines and reminders.<br>
   *Opportunity:* Introduce template-driven outline builders that pre-fill liturgical calendar metadata and integrate with command palette actions.

2. **"The Latin translations live outside Theoria, so our patristics class can't use the same workflow."**<br>
   *Signal:* Multilingual corpora require manual translation alignment, making comparative work slow.<br>
   *Opportunity:* Expand ingestion adapters with translation memory hooks and side-by-side diffing for variant readings.

3. **"Ingestion failures ping my inbox at 2am."**<br>
   *Signal:* Assistants have no consolidated dashboard for job health or retry scheduling.<br>
   *Opportunity:* Add a lightweight operations console with SLA indicators, failure triage queues, and webhook-based notifications.

4. **"Our small group leaders need simplified discussion prompts."**<br>
   *Signal:* Volunteers default to third-party devotionals because Theoria outputs assume deep exegetical training.<br>
   *Opportunity:* Ship persona-specific prompt packs and alternate export formats (e.g., "30-minute discussion guide").

## Opportunity Backlog

| Horizon | Candidate Initiative | Why It Matters | Suggested Next Step |
| --- | --- | --- | --- |
| **Now (0-3 months)** | Collaborative sermon outline export | Reduces external tool hopping for the largest paying segment. | Prototype structured export with verse anchors and meeting agenda fields. |
|  | Ingestion operations console (MVP) | Eliminates manual spreadsheets, improves trust in automated pipelines. | Extend existing metrics scripts into a web dashboard surfaced via `/ops`. |
| **Next (3-6 months)** | Multilingual corpus alignment | Unlocks academic partnerships and grant opportunities. | Spike translation memory integration and evaluate GPU cost envelope. |
|  | Guided discussion exports for lay leaders | Addresses churn risk and expands top-of-funnel adoption. | Design templated prompts, test via Next.js feature flag targeting lay leader role. |
| **Later (6+ months)** | Workspace-level audit logs & collaboration | Required by institutions before rolling out team-wide. | Partner with 1-2 seminaries to define retention + privacy requirements. |
|  | Persona-aware prompt marketplace | Differentiates Theoria's agent workflows while staying verse anchored. | Build prompt governance framework and curation workflow. |

## Research & Validation Actions

- Schedule focused interviews with at least two representatives from each persona above to quantify frequency and impact of the highlighted pain points.
- Instrument existing export, ingestion, and prompt usage paths to capture drop-off moments; pair metrics with qualitative follow-ups.
- Co-design prototypes with the most engaged churches and institutions to ensure new workflows remain scripture-grounded and audit-friendly.
- Revisit this document quarterly; promote validated items into the public roadmap (`docs/ROADMAP.md`) and feature index once execution plans exist.

## Success Metrics to Track

- **Collaboration adoption:** Number of shared sermon outline exports generated per week.
- **Operational health:** Mean time to recover from ingestion failure, percentage of jobs auto-resolved.
- **Translation coverage:** Corpus percentage with aligned parallel translations and associated retrieval accuracy uplift.
- **Lay leader retention:** Repeat session creation rate for small group resources over 60-day cohorts.

Keeping these adjacencies visible helps ensure Theoria grows beyond its excellent retrieval core and supports the broader rhythm of theological research teams.
