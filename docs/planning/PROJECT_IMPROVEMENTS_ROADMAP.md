# Project Improvements Roadmap

> **Created**: 2025-11-21
> **Status**: Active Implementation
> **Priority**: High - Security & Developer Experience

This roadmap addresses critical feedback on the Theoria project setup, prioritized by impact and urgency.

---

## Priority 1: Security Documentation Contradiction (IMMEDIATE)

### Issue
SECURITY.md claims automated DAST (ZAP) is active, while THREATMODEL.md states "No automated DAST yet."

### Impact
Contradictory security documentation erodes trust and creates audit failures.

### Resolution
- Update THREATMODEL.md to reflect current reality (ZAP workflow exists)
- Ensure both documents stay synchronized

### Files
- `THREATMODEL.md` - Update residual risks section

---

## Priority 2: Insecure Default Configuration (HIGH)

### Issue
`THEO_ALLOW_INSECURE_STARTUP=1` and `THEO_AUTH_ALLOW_ANONYMOUS=1` create paths to production without authentication.

### Impact
"Temporary" dev configurations end up in production deployments.

### Resolution
1. Auto-generate a dev API key on startup when none provided
2. Print the generated key to console with clear warnings
3. Never allow the application to boot without some auth mechanism
4. Update documentation to remove references to insecure startup patterns

### Implementation Notes
- Modify `theo/application/facades/runtime.py` to generate ephemeral dev keys
- Update `theo/application/facades/settings.py` to enforce auth requirements
- Update `.env.example` and `README.md` to reflect new patterns

---

## Priority 3: Dependency Management Simplification (MEDIUM)

### Issue
Double-handling dependencies: tight upper bounds in `pyproject.toml` + constraint files creates maintenance burden.

### Impact
Forces constant PRs for minor version bumps, complicates onboarding.

### Resolution
**Recommended: Full `uv` adoption**

1. Remove strict upper bounds in `pyproject.toml` (e.g., `fastapi>=0.119.0,<0.122` → `fastapi>=0.119.0`)
2. Use `uv.lock` as single source of truth for reproducible builds
3. Deprecate `constraints/*.txt` pattern
4. Update documentation to use `uv sync` workflow

### Trade-offs
- **Pro**: Simpler CI, faster dependency resolution, single source of truth
- **Con**: Team must adopt `uv` tooling (already partially in use for PyTorch)

### Migration Path
1. Document recommendation in `docs/planning/`
2. Create ADR for decision
3. Implement in separate PR to avoid blocking other improvements

---

## Priority 4: Test Suite Fragmentation (MEDIUM)

### Issue
11+ test markers suggest a slow/flaky test suite that developers skip locally.

### Impact
Developers rely entirely on CI, reducing feedback loop quality.

### Resolution

### 4.1 Remove `flaky` marker
Tests marked `flaky` teach developers to ignore red builds. Either fix the underlying issue or delete the test.

### 4.2 Consolidate markers
| Current | Proposed | Rationale |
|---------|----------|-----------|
| `db`, `pgvector`, `schema` | `integration` | All require database infrastructure |
| `slow`, `celery`, `e2e` | Keep separate | Distinct infrastructure needs |
| `perf`, `performance` | `perf` | Duplicate markers |
| `gpu`, `contract`, `redteam` | Keep separate | Specialized requirements |

### 4.3 Invert the test pyramid
- Mock DB/vector store for 90% of domain logic tests
- Reserve integration markers for cross-boundary tests only

### Implementation
- Document strategy in testing guidelines
- Create migration plan for existing tests
- Update `pyproject.toml` markers

---

## Priority 5: Privacy & Local LLM Strategy (MEDIUM-HIGH)

### Issue
Cloud LLM reliance creates privacy bottleneck for sensitive theological research data.

### Impact
Disqualifies privacy-conscious users and institutions (counseling notes, prayer journals, draft sermons).

### Resolution
**Elevate Local LLM from "nice-to-have" to Core Requirement**

### 5.1 Architecture Changes
- Default to local embedding/generation (Ollama, vLLM)
- Cloud providers become opt-in "Pro" feature
- Document data flow boundaries clearly

### 5.2 Documentation Updates
- Update THREATMODEL.md to reflect local-first approach
- Add local LLM setup guide
- Document when cloud providers are appropriate

### 5.3 Implementation Phases
1. **Phase 1**: Document local LLM as recommended default
2. **Phase 2**: Add Ollama integration for embeddings
3. **Phase 3**: Add local generation support
4. **Phase 4**: Make cloud providers explicit opt-in

---

## Priority 6: Clean Architecture Trade-offs (LOW)

### Issue
Strict hexagonal architecture creates "Pass-Through Hell" with excessive DTO mapping.

### Impact
Triples code surface area for simple CRUD, reduces development velocity.

### Resolution
**Adopt Pragmatic Clean Architecture**

### Guidelines
1. **Allow domain entities for read-only operations** - Service layer can return domain entities directly for queries
2. **Reserve DTOs for mutations and external contracts** - Use mapping only when strict versioning is required
3. **Document exception cases** - Create ADR explaining when to deviate from strict patterns

### Implementation
- Document guidelines in CLAUDE.md
- Create ADR for architectural flexibility
- Gradually refactor existing pass-through patterns

---

## Implementation Order

### Phase 1: Immediate (This PR)
1. ✅ Fix THREATMODEL.md contradiction
2. ✅ Document roadmap
3. ✅ Add local LLM documentation
4. ✅ Document test consolidation strategy
5. ✅ Document dependency management recommendation
6. ✅ Document architecture trade-offs

### Phase 2: Follow-up PRs
1. Implement auto-generated dev keys (requires careful testing)
2. Consolidate test markers
3. Create uv migration PR
4. Add Ollama integration

### Phase 3: Future Work
1. Local LLM generation support
2. Full test pyramid inversion
3. Architecture refactoring

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Security doc contradictions | 1+ | 0 |
| Insecure startup paths | 2+ | 0 |
| Test markers | 11 | 7 |
| Local development friction | High | Low |
| Privacy-sensitive deployment | Cloud-only | Local-first |

---

## References

- ADR location: `docs/adr/`
- Test documentation: `docs/testing/`
- Security documentation: `SECURITY.md`, `THREATMODEL.md`
- Architecture documentation: `docs/architecture.md`
