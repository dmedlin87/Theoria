# Contracts Module Contract-Test Failures

## Summary

A targeted run of the Schemathesis-based contract tests (`pytest tests/contracts/test_schemathesis.py`) fails for every endpoint that expects a JSON request body. Each failing case returns HTTP 422 with the error payload `{"detail":[{"type":"missing","loc":["body"],"msg":"Field required","input":null}]}` even though the override logic in the test suite supplies a JSON dictionary. The root cause is that the dynamically generated Schemathesis cases have no `media_type` set after the tests mutate `case.body`, so the client issues the request without a JSON content type and FastAPI interprets the body as missing.

All other supporting fixtures (database seeding, guardrail stubs, authentication overrides, etc.) function correctly—the endpoints succeed when invoked directly with a proper JSON payload. The bug therefore lives in the test harness rather than the API implementation.

## Reproduction

```bash
pytest tests/contracts/test_schemathesis.py
```

This produces six failing parametrised cases, all reporting status code 422 instead of their expected 2xx response.【b57609†L1-L40】

## Root Cause Analysis

1. The contract test rewrites the generated Schemathesis case before executing it:
   * The override pipeline injects explicit bodies, path params, and headers into `case.body`, `case.path_parameters`, etc.【F:tests/contracts/test_schemathesis.py†L806-L831】
2. When the mutated case is executed, FastAPI reports a missing request body. Inspecting the response during the failing run shows the JSON validation error for `/ai/chat`, `/ai/citations/export`, and `/settings/ai/providers/{provider}` respectively.【719688†L1-L3】【19b32c†L1-L3】【e5c57a†L1-L3】
3. Probing the failing case inside the debugger reveals that `case.media_type` is `None` after `case.body` is overwritten, so Schemathesis does not send the JSON payload; the request reaches the server without a body and triggers the validation error.【03c732†L1-L3】
4. Calling the same endpoint with the contract test client and the intended JSON body succeeds (status 200), confirming the API itself is healthy.【d63046†L1-L3】

## Impact

All Schemathesis coverage for the contracts module currently fails, so the suite cannot catch regressions in:

- `/ai/chat`
- `/ai/citations/export`
- `/ai/sermon-prep/export`
- `/ai/digest/watchlists`
- `/analytics/feedback`
- `/settings/ai/providers/{provider}`

## Recommendation

Update the contract test harness so that any manual overrides set the request media type before executing the case—for example, assign `case.media_type = "application/json"` whenever a JSON body is provided. Once the Schemathesis client knows the content type, the overridden bodies will be sent correctly and the endpoints will return their expected success responses.
