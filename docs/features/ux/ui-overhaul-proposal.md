# Theoria Web UI Overhaul Proposal

## Executive summary

The current Next.js front end (see `theo/services/web/app/layout.tsx` and `theo/services/web/app/globals.css`) delivers a stable research workspace, yet its structure still resembles the first production-ready iteration. The navigation is a simple horizontal list, the body content is constrained to a single column, and key workflows (chat, search, verse explorer, copilot, upload) each implement their own layout patterns. A comprehensive redesign can elevate the product into a modern, sleek application that feels purpose-built for theological research, while preserving the mature data and workflow foundations already in place.

This proposal outlines a holistic overhaul that introduces a cohesive design system, adaptive information architecture, multi-pane research workspaces, and premium interaction polish. The intent is to ship the redesign incrementally without destabilising existing features, while enabling a new visual language that reflects Theoria's credibility and focus on grounded scholarship.

## Goals and non-goals

### Goals

- Establish a scalable design system with theme tokens, responsive primitives, and consistent component anatomy.
- Provide a unified workspace shell with persistent navigation, contextual secondary menus, and flexible canvas areas for each mode.
- Showcase research artefacts (citations, documents, digests, uploads) with richer information density and affordances for comparison.
- Elevate perception of speed and craft via progressive disclosure, skeleton states, micro-interactions, and motion guidelines.
- Improve accessibility (WCAG 2.2 AA) and internationalisation readiness through semantic markup, contrast-aware theming, and logical focus order.
- Maintain feature parity for core workflows while paving the path for future capabilities (collaboration, collections, timeline views).

### Non-goals

- Rewriting server-side APIs or the chat workflow engine. The focus is the Next.js client.
- Migrating to a different front-end stack; the overhaul stays within the current Next.js + React + CSS tooling.
- Delivering every envisioned feature in one release. The plan emphasises phased delivery with user validation checkpoints.

## Current-state audit

### Layout and navigation

- `app/layout.tsx` renders a sticky header with a centered container and a basic list of nav links. There is no concept of active state, secondary navigation, or quick actions.
- The global container (1120px max width) creates a document-like single column. Dense research UIs (chat, search filters, verse explorer) end up stretching vertically with limited ability to reveal supporting panels.
- Mode switching is isolated in a banner (`<ModeSwitcher />`) beneath the header rather than being integrated into the primary navigation hierarchy.

### Workspace implementations

- The chat feature (`app/chat/ChatWorkspace.tsx`) handles complex state: streaming responses, guardrails, feedback telemetry, and sample prompts. UI responsibilities are tightly coupled with data orchestration in a single component.
- Search, verse explorer, and copilot each define their own grids and card treatments inside their route folders, resulting in inconsistent spacing, typography, and micro-interactions.
- Upload and admin views follow standalone layouts, further deviating from the primary workspace feel.

### Visual language

- `globals.css` defines a light-only theme with static colour variables and gradient backgrounds. There is no dedicated dark mode, spacing scale, or typography ramp beyond global defaults.
- Components rely on bespoke class names rather than reusable utility patterns or an extracted component library, making iterative visual changes costly.
- Iconography, motion, and affordance states are minimal, leading to a utilitarian but unfinished impression.

## Target experience

### Core principles

1. **Purposeful density** – allow scholars to compare references, notes, and model output without endless scrolling by embracing multi-column layouts and resizable panes.
2. **Calm authority** – use a restrained palette, precise typography, and soft depth cues to project trustworthiness befitting academic research.
3. **Guided exploration** – surface contextual wayfinding (breadcrumbs, progress indicators, suggested actions) to help users move between ingestion, study, and synthesis workflows.
4. **Responsive fluency** – ensure the UI scales gracefully from 13" laptops to 4k monitors, with touch-friendly adaptations for tablet usage during teaching or study.

### Shell architecture

- **Left rail**: Introduce a fixed left navigation rail with Theo branding, mode selector, and grouped primary destinations (Workspace, Library, Corpora, Admin). Use icon + label pairs and highlight the active route with a pill indicator.
- **Top command bar**: Add a collapsible command bar hosting global search, quick actions ("New Research Notebook", "Upload Sources"), and status indicators (job queue, notifications).
- **Content canvas**: Replace the single `.container` with a responsive CSS grid that allocates a main canvas, contextual side panels, and bottom drawers. The grid should adapt to breakpoints (≥1440px: 3-column, 1024–1439px: 2-column, <1024px: stacked).
- **Utility footer**: Convert the current footer to a thin utility strip containing legal links, version/build info, and keyboard shortcut hints.

### Workspace patterns

1. **Chat Studio**
   - Multi-pane layout with left conversation list (recent sessions, pinned prompts), center chat thread, right insight panel showing citations, guardrail context, and export options.
   - Floating composer with adaptive height, suggestions chip row, and inline tool picker (voice input, verse insertion, attach files from uploads).
   - Visual treatment for assistant messages emphasising provenance chips, inline verse previews, and quick actions ("Open in Notebook", "Add to Collection").

2. **Search & Library**
   - Unified search results page with sticky filter rail, result cards supporting inline preview, comparison mode (select up to 3 documents to view side-by-side), and quick facets.
   - Saved searches and alerts accessible via a right drawer, leveraging existing telemetry to prioritise frequently used panels.

3. **Verse Explorer**
   - Introduce a two-column layout: canonical text with parallel translations, commentary timeline, and cross references. Add a bottom timeline for historical commentaries sourced from OpenAlex fixtures.

4. **Copilot Workflows**
   - Provide task templates (sermon outline, devotional guide) as cards at the top; selecting a template opens a structured canvas with stepper navigation, summarised progress, and export call-to-actions.

5. **Uploads & Admin**
   - Align ingestion and admin tools with a data-table-forward design system: responsive tables with density toggles, inline editing modals, and a global status toast system for background jobs.

### Visual system

- **Design tokens**: Define colour, typography, spacing, shadow, and border radii tokens in `app/theme.css` (new file). Support light and dark modes via CSS custom properties, toggled through `prefers-color-scheme` and user settings persisted in `ModeProvider`.
- **Type scale**: Adopt a modular scale (e.g., 1.2 ratio) with tokens such as `--font-display-lg`, `--font-body`, etc. Pair with letter-spacing and line-height tokens for readability.
- **Grid & spacing**: Establish an 8px base grid with rem-based spacing tokens (`--space-1` to `--space-8`). Update layout components to consume these tokens instead of hardcoded pixel values.
- **Elevation**: Create a shadow system with semantic levels (`--shadow-sm`, `--shadow-md`, `--shadow-lg`) and apply them consistently across cards, modals, and floating panels.
- **Iconography**: Integrate a consistent icon set (e.g., Phosphor or Lucide) through a lightweight wrapper component.

### Interaction & motion

- Define interaction states (hover, focus, active, disabled) with accessible contrast for all key components (buttons, links, navigation items, table rows).
- Introduce micro-interactions: subtle translations for cards, fade/slide transitions for drawers, skeleton placeholders for streaming chat responses and loading search results.
- Document keyboard navigation patterns (e.g., `Cmd+K` to open command palette, arrow keys to move between panes, `Esc` to close drawers) and integrate with Next.js route-level focus management.

## Implementation plan

### Phase 1 – Foundations (2–3 sprints)

1. **Design token infrastructure**
   - Add `app/theme.css` with light/dark tokens and update `globals.css` to reference the tokens instead of hardcoded values.
   - Extend `ModeProvider` to handle theme toggling (light/dark/system) alongside existing research modes.
2. **Shell scaffolding**
   - Refactor `app/layout.tsx` to render the new left rail, command bar placeholder, and responsive grid container.
   - Implement a `AppShell` component in `app/components/` that manages layout slots (nav, command bar, main, side panel).
3. **Navigation state**
   - Introduce active link detection using Next.js `usePathname` and highlight the relevant nav item.
   - Move mode selection into the left rail with a condensed selector, freeing the main content area.

Deliverable: behind a feature flag (`NEXT_PUBLIC_ENABLE_UI_V2`) to allow user testing alongside existing UI.

### Phase 2 – Workspace realignment (3–4 sprints)

1. **Chat Studio**
   - Break `ChatWorkspace.tsx` into presentation + logic hooks (`useChatSession`, `ChatThread`, `ChatComposer`).
   - Implement conversation list, insight panel, and floating composer using the new grid layout.
   - Add skeleton and streaming states with animation tokens.
2. **Search & Library**
   - Consolidate search UI into a `SearchWorkspace` with shared filter rail component and comparison mode.
   - Migrate verse explorer into the multi-pane layout, ensuring scripture text uses typographic scale tokens.
3. **Copilot templates**
   - Build task template gallery component and restructure flows into stepper-based layouts.

Deliverable: Beta-ready workspace accessible via user toggle, collecting telemetry via existing `emitTelemetry` utilities.

### Phase 3 – Polishing & expansion (2–3 sprints)

1. **Dark mode & accessibility audit**
   - Finalise dark theme values, ensure contrast ratios ≥ 4.5:1, add focus outlines and skip links.
   - Conduct screen reader audit across primary workflows.
2. **Motion & command palette**
   - Implement command palette with keyboard shortcut, quick actions, and integrated search suggestions.
   - Add Lottie or CSS-based animations for guardrail interventions and background job notifications.
3. **Performance & metrics**
   - Optimise layout for Core Web Vitals (LCP, CLS) using Next.js streaming, image optimisation, and code splitting.
   - Update Lighthouse CI baselines (`lighthouserc.json`) once performance improvements are validated.

Deliverable: Public launch of redesigned UI with supporting documentation and release notes.

## Design and engineering collaboration

- Host weekly design-engineering syncs to review component inventory, verify accessibility decisions, and align on telemetry updates.
- Use Storybook (`ChatWorkspace.stories.tsx` already exists) as the canonical playground for new components. Expand coverage to include the navigation shell, cards, tables, and modals.
- Track progress via GitHub project board with vertical slices (e.g., "Shell", "Chat Studio", "Search Compare") to ensure cross-functional visibility.

## Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Feature parity gaps during migration | User confusion, loss of trust | Maintain dual-running feature flag, collect usage analytics, stage rollouts per workspace |
| CSS regressions impacting legacy views | Visual bugs | Adopt visual regression testing via Playwright + Percy; incrementally migrate routes |
| Increased bundle size | Slower load times | Leverage Next.js dynamic imports, tree-shake icon library, monitor bundle analyzer |
| Accessibility regressions | Compliance issues | Integrate Axe automated checks into CI, schedule manual audits before each phase release |

## Success metrics

- **Engagement**: +25% increase in average session length for research workflows, measured via telemetry events.
- **Efficiency**: 30% reduction in time-to-first-citation in chat sessions (measure from `chat.submit` to first assistant message with citations).
- **Adoption**: ≥60% of active users opt into the new UI within the first month of beta availability.
- **Quality**: Lighthouse performance score ≥ 90 for `chat`, `search`, and `copilot` routes in both light and dark modes.
- **Support**: 40% decrease in support tickets related to navigation or "can't find" issues.

## Next steps

1. Align with product and research stakeholders on visual direction (mood boards, high-fidelity mockups).
2. Create a component inventory audit documenting current styles vs. target tokens.
3. Kick off Phase 1 implementation with shell scaffolding behind feature flag and begin usability testing with internal theologians.

With this roadmap, Theoria's interface can evolve into a refined, modern research environment that matches the sophistication of its underlying retrieval and generative systems.
