# Newly Identified Maintenance Tasks

## Typo fix task
- **Location**: `docs/more_features.md`
- **Issue**: The goal statement reads "evidence-on tap", leaving a stray hyphen that splits the phrase awkwardly.
- **Proposed task**: Replace the fragment with "evidence on tap" (or add the closing hyphen) so the sentence reads naturally.

## Bug fix task
- **Location**: `theo/services/api/app/routes/realtime.py`
- **Issue**: `NotebookEventBroker.disconnect` never removes empty connection sets because the guard `if connections and not connections` short-circuits once the set becomes empty, so notebook IDs linger in `_connections`.
- **Proposed task**: Update the condition to drop the key when the set exists but is empty (e.g., `if connections is not None and not connections:`) so idle notebooks release resources.

## Documentation correction task
- **Location**: `docs/API.md`
- **Issue**: The introduction still claims "Authentication: not required", but the README and API defaults now require API keys or explicit anonymous mode.
- **Proposed task**: Revise the authentication note to explain the current credential requirements and how to enable anonymous access for development.

## Test improvement task
- **Location**: `theo/services/api/tests/test_features.py`
- **Issue**: The tests only assert that a few flags exist; they never toggle environment-driven options like `verse_timeline` or `contradictions` to ensure the routes honor settings overrides.
- **Proposed task**: Monkeypatch `get_settings()` (or environment variables) inside the tests to verify the responses flip when optional features are disabled or enabled.
