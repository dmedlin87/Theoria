# Potential Maintenance Tasks

## Fix typo in product vision doc
- **Issue**: `docs/more_features.md` describes "citable evidence-on tap" in the goal statement, which includes a stray hyphen that breaks the phrase.
- **Why it matters**: Cleaning up the typo improves readability in a public-facing proposal.
- **Proposed task**: Replace "evidence-on" with "evidence on" in the goal sentence.
- **Context**: [`docs/more_features.md`](more_features.md) line 3. 【F:docs/more_features.md†L3-L4】

## Allow reranker to recover after transient load failures
- **Issue**: `_resolve_reranker` in the search route caches a failed load by setting `_RERANKER_FAILED = True`. Subsequent calls short-circuit whenever the model path/digest stay the same, so the reranker never retries even if the artifact becomes available later (for example after a delayed download or redeploy).
- **Why it matters**: A temporary filesystem or checksum issue can permanently disable reranking until the API process restarts, degrading search quality.
- **Proposed task**: Adjust the reranker cache to retry after failures—e.g., clear `_RERANKER_FAILED` once the underlying file changes or introduce a time-based backoff instead of a permanent latch.
- **Context**: [`theo/services/api/app/routes/search.py`](../theo/services/api/app/routes/search.py) lines 46-76. 【F:theo/services/api/app/routes/search.py†L46-L136】

## Update feature discovery documentation
- **Issue**: The API guide shows `/features` returning only four keys, but the implementation exposes additional toggles (cross references, textual variants, morphology, verse timeline, etc.), so the example response is outdated.
- **Why it matters**: Accurate examples help client developers understand which flags they can rely on without inspecting the source.
- **Proposed task**: Refresh the example JSON in `docs/API.md` to reflect the full response (or note that additional keys may be present), and mention the newer flags.
- **Context**: [`docs/API.md`](API.md) lines 658-665 vs. [`theo/services/api/app/routes/features.py`](../theo/services/api/app/routes/features.py) lines 9-33. 【F:docs/API.md†L647-L665】【F:theo/services/api/app/routes/features.py†L9-L33】

## Strengthen feature flag tests
- **Issue**: `test_features.py` only asserts that certain keys exist in the payloads. It does not validate that environment-driven flags (e.g., `contradictions_enabled`, `geo_enabled`) toggle the responses, leaving regressions undetected.
- **Why it matters**: Adding assertions around flag flipping ensures the API contract stays in sync with configuration.
- **Proposed task**: Extend the tests to monkeypatch `get_settings()` or environment variables and confirm `/features` and `/features/discovery` reflect both enabled and disabled states for optional capabilities.
- **Context**: [`theo/services/api/tests/test_features.py`](../theo/services/api/tests/test_features.py) lines 8-24. 【F:theo/services/api/tests/test_features.py†L1-L24】
