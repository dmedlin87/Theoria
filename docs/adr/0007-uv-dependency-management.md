# ADR 0007: Migrate to uv for Dependency Management

- Status: Proposed
- Date: 2025-11-21

## Context

Current dependency management uses a "double-handled" approach:

1. **pyproject.toml** - Defines dependencies with strict upper bounds (e.g., `fastapi>=0.119.0,<0.122`)
2. **constraints/*.txt** - Lockfiles for reproducible builds

This creates maintenance burden:
- Minor version bumps require updating both locations
- Tight upper bounds force frequent PRs for version updates
- Dependency resolution conflicts occur in two places
- Onboarding complexity is high

The project already uses `uv` for PyTorch index resolution (`tool.uv` section in pyproject.toml), indicating partial adoption.

## Decision

**Go all-in on `uv` as the single dependency management tool.**

### Changes

1. **Loosen version bounds in pyproject.toml**:
   - Change `fastapi>=0.119.0,<0.122` to `fastapi>=0.119.0`
   - Remove tight upper bounds that don't reflect actual API breakages
   - Keep lower bounds for known compatibility requirements

2. **Use uv.lock as single source of truth**:
   - Replace `constraints/*.txt` with `uv.lock`
   - Single lockfile for all environments
   - Reproducible builds via `uv sync`

3. **Simplify installation commands**:
   ```bash
   # Before
   pip install ".[api]" ".[ml]" ".[dev]" -c constraints/prod.txt -c constraints/dev.txt

   # After
   uv sync --all-extras
   ```

4. **Update CI workflows**:
   - Use `uv sync` instead of pip with constraints
   - Faster dependency resolution
   - Better error messages

### Migration Path

1. Generate initial `uv.lock` from current constraints
2. Test in CI with both old and new approaches
3. Update documentation
4. Deprecate constraints/ directory
5. Remove old approach after validation period

## Consequences

### Benefits
- Single source of truth for dependency versions
- Faster dependency resolution (uv is significantly faster than pip)
- Simpler onboarding: one command instead of three
- Reduced maintenance burden for version bumps
- Better error messages and conflict resolution

### Trade-offs
- Team must adopt uv tooling
- Transition period with both systems
- Some CI environments may not have uv pre-installed

### Compatibility
- uv is compatible with pyproject.toml standards
- Can fall back to pip + constraints if needed
- uv.lock is human-readable and diffable

## Implementation

See `docs/planning/PROJECT_IMPROVEMENTS_ROADMAP.md` Priority 3 for migration plan.

## References

- [uv documentation](https://docs.astral.sh/uv/)
- Current `tool.uv` configuration in `pyproject.toml`
- `scripts/update_constraints.py` - Current constraint generation
