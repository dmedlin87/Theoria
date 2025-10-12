# Red-team Guardrail Quality Analysis

Date: 2025-10-11 00:21 UTC

## Summary
- The dedicated OWASP-focused red-team regression suite passes in full, covering chat, verse, and sermon-prep guardrail behaviours against hostile prompts.【F:tests/redteam/test_ai_redteam.py†L29-L156】
- Deterministic refusal fixtures enforce citation integrity and sensitive-content filtering, ensuring guardrail regressions surface immediately during test runs.【F:tests/redteam/harness.py†L14-L145】【F:tests/redteam/prompts.py†L1-L21】
- Pytest reports only pre-existing third-party warnings (Pydantic alias metadata and SQLAlchemy drop-order hints); no Theoria code regressions were detected.【50e7f6†L1-L24】

## Commands Executed

```bash
pytest -m redteam -q
```
Result: ✅ 20 passed, 417 deselected, 5 warnings (external/library).【50e7f6†L1-L24】

## Follow-Up Recommendations
- Track upstream fixes for the Pydantic `validation_alias` warning to avoid noise in guardrail CI jobs; consider adjusting affected field definitions if upstream remains unchanged.【50e7f6†L8-L16】
- Investigate SQLAlchemy's metadata drop-order warning emitted by the test teardown and evaluate whether applying `use_alter=True` or explicit fixture scoping can eliminate unnecessary migration noise.【50e7f6†L17-L22】
- Continue running the red-team suite on every guardrail-related change to maintain refusal and citation guarantees documented in the harness and test cases.【F:tests/redteam/harness.py†L57-L145】【F:tests/redteam/test_ai_redteam.py†L66-L199】
