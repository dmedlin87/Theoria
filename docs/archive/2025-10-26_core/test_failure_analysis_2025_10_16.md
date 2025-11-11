> **Archived on 2025-10-26**

# Test Failure Analysis (2025-10-16)

This document summarizes the test failures and errors from the test run on October 16, 2025.

## High-Level Summary

-   **Total Failures**: 21
-   **Total Errors**: 16
-   **Primary Themes**:
    1.  **Configuration/Secrets**: Multiple tests, especially in `test_ai_redteam.py`, are failing due to a missing `SETTINGS_SECRET_KEY`, which prevents the application from decrypting settings.
    2.  **API Signature Changes**: The `handle_note_write` function signature in the MCP tools has changed, breaking several integration tests.
    3.  **Data Formatting**: A citation formatting test is failing due to a missing comma, indicating a regression in the SBL citation style implementation.
    4.  **Database/Query Logic**: A test for contradiction searching (`test_search_contradictions_uses_range_filters`) is failing an assertion on the number of SQL queries executed.
    5.  **Recursion Error**: Monkeypatching in `test_api_mcp_integration.py` is causing an infinite recursion loop.

---

## Detailed Failure Analysis

### 1. Cryptography & Settings Failures (`RuntimeError: Failed to decrypt persisted setting`)

-   **Files Affected**:
    -   `tests/redteam/test_ai_redteam.py`
    -   `theo/application/facades/settings_store.py`
-   **Cause**: The test environment is not configured with a `SETTINGS_SECRET_KEY`. The `_decrypt_value` function in `settings_store.py` catches a `cryptography.fernet.InvalidToken` exception and raises a generic `RuntimeError`. This prevents the LLM registry from being initialized, causing a cascade of failures in dependent tests.
-   **Affected Tests**:
    -   `test_chat_prompt_sanitises_adversarial_inputs`
    -   `test_chat_guard_rejects_sql_leak`
    -   All `test_chat_refuses_owasp_prompts` and related workflow tests.

### 2. MCP Tools API Regression (`TypeError` & `RecursionError`)

-   **Files Affected**:
    -   `tests/mcp_tools/test_api_mcp_integration.py`
    -   `theo/infrastructure/api/app/mcp/tools.py`
-   **Cause**:
    -   `TypeError`: The function `handle_note_write` no longer accepts the `resolve_document_osis` keyword argument, but tests are still passing it.
    -   `RecursionError`: The monkeypatch for `_resolve_document_osis` in `TestResolveDocumentOsis` is incorrectly implemented, causing the function to call itself endlessly.
-   **Affected Tests**:
    -   `TestHandleNoteWrite.test_doc_id_used_when_osis_missing`
    -   `TestHandleNoteWrite.test_missing_osis_raises_error`
    -   `TestResolveDocumentOsis.test_prefers_primary_reference`
    -   `TestResolveDocumentOsis.test_falls_back_to_first_osis`
    -   `TestResolveDocumentOsis.test_returns_none_when_no_rows`

### 3. Citation Formatting Error (`AssertionError`)

-   **File Affected**: `tests/export/test_citation_formatters.py`
-   **Cause**: The generated citation string `Doe, Jane and John Smith...` is missing a comma after "Jane", which is present in the expected output `Doe, Jane, and John Smith...`. This points to a logic error in the SBL author list formatter.
-   **Affected Test**: `test_build_citation_export_sbl`

### 4. Note Creation `KeyError`

-   **File Affected**: `tests/mcp_tools/test_write_tools.py`
-   **Cause**: The `create_research_note` function (mocked in the test) is not being called with the `request_id` argument, leading to a `KeyError` when the test tries to assert its value.
-   **Affected Test**: `test_note_write_commit_invokes_creator`

### 5. Seed Query Logic Failure (`AssertionError`)

-   **File Affected**: `tests/research/test_seed_queries.py`
-   **Cause**: The test `test_search_contradictions_uses_range_filters` asserts that two `SELECT` statements should be executed, but only one is. This suggests a logic change in how `search_contradictions` applies filters or constructs its query.
-   **Affected Test**: `test_search_contradictions_uses_range_filters`

---

## Recommendations

1.  **Fix Configuration**: Set the `SETTINGS_SECRET_KEY` in the test environment configuration or mock the decryption layer to unblock the red team and AI-related tests.
2.  **Update MCP Tool Tests**:
    -   Remove the `resolve_document_osis` argument from calls to `handle_note_write`.
    -   Correct the monkeypatch in `TestResolveDocumentOsis` to avoid recursion.
    -   Ensure `request_id` is passed through correctly during note creation.
3.  **Correct Citation Formatter**: Fix the author-joining logic in the SBL citation formatter to correctly handle commas between multiple authors.
4.  **Investigate Seed Query**: Debug `search_contradictions` to understand why the second query is not being executed when filtering by perspective.
