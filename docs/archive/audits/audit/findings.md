# Review Findings

## Typo fix task
- **Location**: `theo/infrastructure/api/app/ai/rag/guardrails.py`
- **Issue**: The guardrail error message spells “unparseable” with an extra “e”, which isn’t the preferred spelling elsewhere in the project and reads like a typo.
- **Proposed task**: Update the message to use the conventional spelling “unparsable” (and adjust related tests if needed) to keep user-facing copy polished.

## Bug fix task
- **Location**: `theo/infrastructure/api/app/export/formatters.py`
- **Issue**: When callers pass field filters such as `{"metadata.title"}`, the formatter drops the entire `metadata` block before `_filter_values` can trim nested keys, so filtered exports can never include metadata.
- **Proposed task**: Respect nested metadata selections by keeping the `metadata` object when sub-fields are requested, letting `_filter_values` perform the final pruning.

## Documentation correction task
- **Location**: `docs/API.md`
- **Issue**: The `GET /research/contradictions` section omits the `perspective` query parameter that the FastAPI route already supports.
- **Proposed task**: Document the `perspective` list parameter (with the allowed values) so client developers discover the full filtering surface.

## Test improvement task
- **Location**: `theo/services/web/tests/app/api/search/route.test.ts`
- **Issue**: The proxy tests assert API key handling but never verify that trace headers (forwarded by `forwardTraceHeaders`) propagate to the Next.js response.
- **Proposed task**: Extend the suite with a mock response that includes `x-request-id`/trace headers and assert that `GET` returns them, protecting the tracing contract.
