# UX Review

## Highlights
- The dashboard greets users with contextual metadata, provides manual refresh controls, and surfaces load/error states through accessible status messaging. 【F:theo/services/web/app/dashboard/DashboardClient.tsx†L94-L144】
- The system health card announces adapter status changes via `aria-live`, color-coded badges, and latency metadata that help operators triage outages quickly. 【F:theo/services/web/app/dashboard/components/SystemHealthCard.tsx†L206-L251】
- The chat workspace communicates the active reasoning mode with labelled radio groups and offers quick navigation to adjacent research tools, reinforcing the broader workflow. 【F:theo/services/web/app/chat/ChatWorkspace.tsx†L650-L756】

## Issues & Recommendations

1. **Dashboard metrics panel renders an empty void during the first load.**
   - When no cached dashboard data exists, the metrics grid receives `loading=true` and an empty array; the component skips both the loading caption and the empty state copy, leaving a blank section bounded by heavy chrome. 【F:theo/services/web/app/dashboard/DashboardClient.tsx†L121-L144】【F:theo/services/web/app/dashboard/components/MetricsGrid.tsx†L25-L57】
   - *Recommendation:* Add a skeleton, spinner, or descriptive message while metrics are loading so the user understands data is on the way.

2. **Quick actions column lacks an empty-state affordance.**
   - If the API returns zero quick actions, the section still renders the heading but no list items, which can look like broken UI. 【F:theo/services/web/app/dashboard/components/QuickActionsPanel.tsx†L9-L30】
   - *Recommendation:* Render guidance (for example, “No shortcuts yet—open a notebook to pin it here”) or hide the card entirely when there are no actions.

3. **Quick stats fallback values can mislead.**
   - Missing metrics default to `0`, while loading metrics show an ellipsis; both appear alongside percentage deltas, implying legitimate measurements rather than unavailable data. 【F:theo/services/web/app/dashboard/components/QuickStats.tsx†L32-L68】
   - *Recommendation:* Treat missing metrics as “Not available” with muted styling so users do not misinterpret the placeholders as real counts.

4. **Chat hero dominates vertical space after conversations begin.**
   - The static overview (mode chooser, highlights, and three callouts) continues to render above every transcript, forcing returning users to scroll before seeing new replies. 【F:theo/services/web/app/chat/ChatWorkspace.tsx†L650-L756】
   - *Recommendation:* Collapse the hero once the user has an active transcript, or move it into a dismissible panel so the conversation remains at the top of the viewport.

5. **Chat empty state stacks three primary CTAs without prioritisation.**
   - Uploading, browsing examples, and watching a video all appear as equally weighted buttons, which can overwhelm new users deciding what to do first. 【F:theo/services/web/app/chat/ChatWorkspace.tsx†L883-L915】
   - *Recommendation:* Elevate a single primary follow-up (for example “Upload sources”) and demote secondary links to text buttons or inline links for clearer guidance.
