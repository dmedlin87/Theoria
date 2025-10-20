# Contracts Module Contract-Test Status

## Status

- **Resolved** – Schemathesis overrides now set `case.media_type = "application/json"` whenever a JSON body is injected, ensuring FastAPI receives the payload during contract test runs.【F:tests/contracts/test_schemathesis.py†L819-L834】

## Verification

```bash
pytest tests/contracts/test_schemathesis.py -k "ai/chat" -q
```

The focused run now passes, confirming the contract harness delivers JSON request bodies correctly.【e606af†L1-L2】

## Historical Context

Earlier runs of the Schemathesis suite failed for every endpoint expecting JSON because overriding `case.body` removed the associated media type. Without a JSON content type FastAPI treated the body as missing and returned HTTP 422 validation errors. The fix restores the media type after overrides so that each contract case faithfully reproduces the expected request. All supporting fixtures (database seeding, guardrail stubs, authentication overrides, etc.) continue to operate as designed—the bug existed solely in the test harness configuration.
