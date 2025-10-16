# Case Builder

> **Status:** Planned  
> **Version:** v4  
> **Last Updated:** October 2025

## Overview

The Case Builder is a planned feature that will automatically discover patterns, contradictions, and connections across your theological research corpus. It monitors document ingestion and creates actionable insights when multiple sources converge on themes or when conflicts emerge.

## Current Specification

The authoritative specification is **Case Builder v4**, located at:
`docs/archive/planning/case-builder/case builder v4.md`

This implementation plan outlines a phased rollout:

### Phase 0: Domain Model & Ingestion (Weeks 0-1)
- SQLAlchemy models for case objects, sources, edges, insights, and actions
- Integration with existing ingestion pipeline
- Postgres NOTIFY events and Celery task stubs

### Phase 1: Convergence Insights (Weeks 1-2)
- Similarity-based pattern detection using pgvector
- FastAPI router and WebSocket support
- Minimal Next.js insight feed UI

### Phase 2: Graph Signals & Explainability (Weeks 3-4)
- Graph-derived features (Adamic-Adar, clustering, Jaccard, PMI)
- Reciprocal Rank Fusion across multiple signals
- "Why it fired" explainers in UI

### Phase 3: Collision Detection & Personalization (Weeks 5-6)
- Contradiction detection across sources
- User feedback loop (Accept/Snooze/Mute/Bundle)
- Per-user scoring personalization

### Phase 4: Bundling & Momentum (Weeks 7-8)
- Bayesian surprise tracking
- Multi-day momentum aggregation
- Timeline views and topic heatmaps

## Schema

The canonical schema is defined in `docs/case_builder.schema.json` with sample fixtures:
- `fixtures/case_builder/sample_convergence.json`
- `fixtures/case_builder/sample_bundle.ndjson`
- `fixtures/case_builder/bundle_record.json`
- `fixtures/case_builder/collision_records.ndjson`
- `fixtures/case_builder/convergence_record.json`

## Related Documentation

### Archived Versions
Historical specifications are preserved in `docs/archive/planning/case-builder/`:
- **v4** (current) - case builder v4.md
- **v2** - case builder v2.md
- **v1** - case-builder-v1.md
- **Buddy Summary** - case_builder_buddy_summary.md
- **Convergence Triggers Blueprint** - theo_engine_case_builder_buddy_convergence_triggers_blueprint.md

### Integration Points
- **Ingestion Pipeline:** `theo/services/api/app/ingest/`
- **Worker Tasks:** `theo/services/api/app/workers/tasks.py`
- **Vector Search:** pgvector embeddings from existing passages
- **API Routes:** `theo/services/api/app/routes/insights.py` (planned)
- **UI:** Next.js insight feed at `/insights` (planned)

## Development Status

This feature is **not yet implemented**. The v4 specification provides a complete implementation roadmap. When development begins, this document will be updated to reflect:
- Implementation progress
- API endpoints
- UI routes
- Configuration options
- User documentation

## Design Principles

The Case Builder follows Theoria's core principles:
1. **Deterministic First:** Pattern detection should be explainable and reproducible
2. **Citation Grounded:** Every insight must trace back to source documents
3. **User Controlled:** Researchers can accept, snooze, mute, or bundle insights
4. **Progressive Enhancement:** Basic similarity matching first, then graph features, then ML personalization
5. **Privacy Aware:** All discovery happens locally on user's corpus

## Questions or Feedback

For questions about the Case Builder specification or to contribute to its design, please:
1. Review the v4 specification in the archive
2. Check related fixture examples for concrete use cases
3. Consult the implementation guide for integration patterns
4. Open an issue or discussion for clarifications
