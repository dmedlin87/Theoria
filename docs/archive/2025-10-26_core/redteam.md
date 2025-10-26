> **Archived on 2025-10-26**

# Red-team guardrail regression suite

The Theoria API ships with an automated OWASP-inspired red-team harness that
exercises the critical `/ai/*` workflows. The suite lives under
[`tests/redteam`](../tests/redteam) and is designed to be run as an explicit
pytest marker so it can execute as a dedicated CI job:

```bash
pytest -m redteam
```

## What the suite covers

* Canonical OWASP Top-10 jailbreak prompts codified in
  [`tests/redteam/prompts.py`](../tests/redteam/prompts.py).
* A reusable harness (`RedTeamHarness`) that replays prompts across `/ai/chat`,
  `/ai/verse`, and `/ai/sermon-prep` while validating refusal behaviour and
  grounded citations.
* Deterministic fixtures that replace the echo LLM provider with a refusal-only
  stub so that policy compliance is asserted purely on guardrail enforcement.

## Adding the job to CI

1. Ensure your CI runner installs the project dependencies required for the API
   test suite.
2. Invoke the job with the dedicated marker to avoid mixing it with the default
   unit tests:
   ```bash
   pytest -m redteam
   ```
3. Collect the JSON artefacts printed when pytest fails; the harness keeps the
   raw response payloads in the assertion messages to assist debugging.

## Triage checklist

When a red-team probe fails:

1. **Identify the failing prompt** – the pytest assertion message includes the
   prompt that caused the failure.
2. **Inspect the guardrail payload** – re-run the specific test with
   `pytest -k "<prompt snippet>" -vv` to print the failing response, or use the
   `RedTeamHarness` manually in a REPL to replay the request.
3. **Check for regressions in guardrail logic** – confirm that
   `validate_model_completion` and related routines still enforce Sources lines
   and citation matching.
4. **Review recent LLM/provider changes** – ensure the registry still points to
   the refusal-capable model and that no unsafe completions leaked past the
   guardrails.
5. **Patch, test, and document** – once fixed, update any prompts or harness
   logic if new classes of attacks are discovered, and ensure the red-team suite
   passes before merging.

Keeping this suite green ensures Theoria continually resists prompt
injection, data exfiltration, and harmful-content requests.
