# ADR 0006: Local LLM-First Architecture

- Status: Proposed
- Date: 2025-11-21

## Context

Theoria handles sensitive theological research data including:
- Counseling notes with private congregation details
- Prayer journals
- Draft sermons
- Personal study notes

Current architecture relies on cloud LLM providers (OpenAI, Anthropic) as the default, with "anonymization via prompt engineering" listed as a mitigation. This approach has significant risks:

1. **Brittle privacy protection** - Prompt-based anonymization is historically unreliable
2. **Data retention concerns** - Third-party providers may retain data beyond our control
3. **Institutional disqualification** - Privacy-conscious users and organizations cannot adopt the platform

## Decision

**Elevate local LLM inference from "nice-to-have" to core requirement.**

### Architecture Changes

1. **Default to local inference**:
   - Embeddings: Local BAAI/bge-m3 (already supported)
   - Generation: Ollama or vLLM as primary option
   - Vector storage: Local PostgreSQL with pgvector

2. **Cloud providers become opt-in**:
   - Treat as "Pro" feature requiring explicit configuration
   - Document clearly when cloud providers are appropriate
   - Require user acknowledgment of data handling implications

3. **Document data flow boundaries**:
   - Clear separation between local-only and cloud-enabled features
   - Audit logging for any external API calls
   - Configuration to completely disable cloud features

### Implementation Phases

| Phase | Scope | Timeline |
|-------|-------|----------|
| 1 | Document local-first as recommended default | Immediate |
| 2 | Add Ollama integration for embeddings | Near-term |
| 3 | Add local generation support (Ollama/vLLM) | Medium-term |
| 4 | Make cloud providers explicit opt-in | Future |

## Consequences

### Benefits
- Privacy-sensitive deployments become possible
- Institutional adoption unblocked
- Full data sovereignty for users
- Reduced operational costs (no API fees)
- Offline capability

### Trade-offs
- Higher local compute requirements
- Initial setup complexity for non-technical users
- Generation quality may differ from cloud models
- Maintenance burden for model updates

### Migration Impact
- Existing users with cloud API keys continue working
- New installations default to local-only
- Documentation updated to recommend local setup first

## References

- `THREATMODEL.md` - Residual risk for cloud LLM data retention
- `docs/planning/PROJECT_IMPROVEMENTS_ROADMAP.md` - Priority 5
- `theo/application/facades/settings.py` - LLM configuration
