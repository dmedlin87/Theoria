# Quick Start for Incoming Agents

[⬅️ Back to the README](README.md)

This quick start compiles the essential steps pulled from the historical agent handoff guides and the current repository layout. Use it to get oriented quickly, then follow the linked deep dives for implementation detail.

---

## 1. Confirm Your Baseline
- Skim the high-level capabilities and tech stack in [`README.md`](README.md).
- Review launch automation in [`START_HERE.md`](START_HERE.md) to choose between the one-command launcher and manual scripts.
- Check the living architecture context in [`AGENT_CONTEXT.md`](AGENT_CONTEXT.md) for code structure, conventions, and active surfaces.

## 2. Set Up the Environment
1. Create a Python 3.12 virtual environment and install extras following the Quick Start in the README.
2. From `theo/services/web`, run `npm install` to prepare the Next.js workspace.
3. Export API keys or enable anonymous development mode as described in the README Quick Start.
4. Launch the API (`uvicorn theo.infrastructure.api.app.main:app --reload`) and Web UI (`npm run dev`) or use `./start-theoria.ps1` for automation.

> ℹ️ **Need HTTPS or Compose?** The launcher profiles in `START_HERE.md` cover HTTPS dev certs, alternate ports, and Docker Compose fallbacks.

## 3. Load Current Context
- Read [`AGENT_CONTEXT.md`](AGENT_CONTEXT.md) for architecture patterns, discovery engine conventions, and tooling expectations.
- Reference [`docs/next_steps_plan.md`](docs/next_steps_plan.md) for the active work queue (stabilize contradiction migrations, harden ingest URL handling, router dedup fixes).
- Use [`IMPLEMENTATION_CONTEXT.md`](IMPLEMENTATION_CONTEXT.md) when you need deeper historical rationale or example snippets.

## 4. Execute with Confidence
- Follow repo-wide conventions from [`CONTRIBUTING.md`](CONTRIBUTING.md), including testing (`task test:fast`, `pytest`) and linting expectations.
- Consult the documentation map in the README plus `docs/INDEX.md` whenever you need feature-specific specs.
- When committing, summarize notable documentation or behavior changes in [`CHANGELOG.md`](CHANGELOG.md) to keep the historical record fresh.

## 5. Stay In Sync
- New to the codebase? Review the latest entries in [`CHANGELOG.md`](CHANGELOG.md) for recent infrastructure and tooling updates.
- If you produce new handoff material, store it under `docs/archive/handoffs/` so the root stays clean.
- Update [`docs/document_inventory.md`](docs/document_inventory.md) whenever the canonical document set shifts.

---

**Next stop:** dive into [`AGENT_CONTEXT.md`](AGENT_CONTEXT.md) for the detailed architecture overview, then return to the [README](README.md) as the canonical entry point for platform positioning and capability highlights.
