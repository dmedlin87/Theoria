# Proposed follow-up tasks

## Fix typo in product vision goal
- **Location**: `docs/more_features.md`
- **Issue**: The goal statement says "citable evidence-on tap" with an extra hyphen that breaks the phrase.
- **Why it matters**: Polishing copy in public-facing vision docs keeps the messaging professional.
- **Suggested fix**: Replace "evidence-on" with "evidence on" in the goal sentence.
- **References**: [`docs/more_features.md`](../docs/more_features.md) line 3. 

## Make reranker retry after transient load failures
- **Location**: `theo/infrastructure/api/app/routes/search.py`
- **Issue**: `_RerankerCache.resolve()` latches `_RERANKER_CACHE.failed = True` after the first load error and never retries while the cache key stays the same, so temporary filesystem or checksum issues permanently disable reranking until the process restarts.
- **Why it matters**: Allowing retries ensures search quality recovers automatically once the model artifact becomes available.
- **Suggested fix**: Clear the `failed` flag when enough time has passed or when the backing file hash changes so `_resolve_reranker` can attempt to load again.
- **References**: [`theo/infrastructure/api/app/routes/search.py`](../theo/infrastructure/api/app/routes/search.py) lines 47-84.

## Update feature discovery documentation
- **Location**: `docs/API.md`
- **Issue**: The documented `/features` response lists only four keys, but the route currently exposes additional toggles (cross references, textual variants, morphology, verse timeline, etc.), so the example payload is stale.
- **Why it matters**: Accurate examples help client developers rely on the available feature flags without inspecting the source.
- **Suggested fix**: Expand the example JSON (or add a note) to reflect the full set of flags returned by `list_features()`.
- **References**: [`docs/API.md`](../docs/API.md) lines 647-665 and [`theo/infrastructure/api/app/routes/features.py`](../theo/infrastructure/api/app/routes/features.py) lines 12-44.

## Strengthen feature flag tests
- **Location**: `theo/services/api/tests/test_features.py`
- **Issue**: The test suite only asserts that certain keys exist in the payloads; it never toggles environment-driven settings such as `contradictions_enabled` or `geo_enabled`, so configuration regressions would slip through.
- **Why it matters**: Exercising flag flips ensures API responses stay aligned with settings.
- **Suggested fix**: Monkeypatch `get_settings()` (or related environment variables) so the tests assert both enabled and disabled states for optional flags in `/features` and `/features/discovery`.
- **References**: [`theo/services/api/tests/test_features.py`](../theo/services/api/tests/test_features.py) lines 1-24 and [`theo/infrastructure/api/app/routes/features.py`](../theo/infrastructure/api/app/routes/features.py) lines 12-44.

## Update CLI documentation spelling consistency
- **Location**: `docs/CLI.md`
- **Issue**: The supported sources section uses the British spelling "recognises" even though the rest of the developer docs adopt American English, which reads like a typo in context.
- **Why it matters**: Keeping terminology consistent avoids distracting nits during reviews and keeps the docs feeling polished.
- **Suggested fix**: Change the verb to "recognizes" in the supported sources bullet list.
- **References**: [`docs/CLI.md`](../docs/CLI.md) line 12. 【F:docs/CLI.md†L12-L20】

## Ensure decrypted credentials helper returns a defined value on failure
- **Location**: `theo/services/web/app/lib/api-config-store.ts`
- **Issue**: `decryptData()` logs an error when AES-GCM decryption fails but exits without returning anything, so callers receive `undefined` even though the signature promises `object | null`.
- **Why it matters**: The mismatch can surface as flaky behavior if future callers rely on the declared return type, so we should explicitly return `null` on failure.
- **Suggested fix**: Update the catch block to return `null` (and add a test) so the helper always fulfills its contract.
- **References**: [`theo/services/web/app/lib/api-config-store.ts`](../theo/services/web/app/lib/api-config-store.ts) lines 120-171. 【F:theo/services/web/app/lib/api-config-store.ts†L120-L171】

## Align ingest UI hint with CLI defaults
- **Location**: `theo/services/web/app/upload/components/SimpleIngestForm.tsx`
- **Issue**: The hint text tells users the CLI defaults to the “Theoria” author, but the CLI actually sets `DEFAULT_AUTHOR = "Theo Engine"`, so the help copy is wrong.
- **Why it matters**: Accurate guidance prevents confusion when users compare UI output with CLI runs.
- **Suggested fix**: Update the hint (or the CLI default) so both surfaces agree on the default author label.
- **References**: [`SimpleIngestForm.tsx`](../theo/services/web/app/upload/components/SimpleIngestForm.tsx) lines 186-188 and [`ingest_folder.py`](../theo/services/cli/ingest_folder.py) lines 56-58. 【F:theo/services/web/app/upload/components/SimpleIngestForm.tsx†L186-L188】【F:theo/services/cli/ingest_folder.py†L56-L58】

## Add coverage for HTTP retry behavior
- **Location**: `theo/services/web/tests/lib/http.vitest.ts`
- **Issue**: The Vitest suite exercises success paths and header merging but never asserts that `createHttpClient` retries network failures according to the `retries` option, leaving the exponential backoff branch untested.
- **Why it matters**: Without a regression test, changes to the retry loop could silently break resiliency.
- **Suggested fix**: Introduce a test that forces fetch to fail, asserts the retry timing/count, and verifies `notifyHttpError` only fires on the terminal failure.
- **References**: [`http.vitest.ts`](../theo/services/web/tests/lib/http.vitest.ts) lines 33-113. 【F:theo/services/web/tests/lib/http.vitest.ts†L33-L113】
