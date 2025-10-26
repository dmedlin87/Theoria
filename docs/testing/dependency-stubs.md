# Test dependency stubs

The root `conftest.py` no longer installs module stubs automatically.  Instead we
provide opt-in fixtures that tests can request when they need lightweight
stand-ins for optional dependencies.

## Available fixtures

| Fixture | Provides |
| --- | --- |
| `stub_sqlalchemy` | In-memory stand-in for ``sqlalchemy`` and common submodules. |
| `stub_pythonbible` | Minimal ``pythonbible`` module exposing ``Book`` and ``NormalizedReference`` helpers. |
| `stub_cryptography` | Stub ``cryptography.fernet`` implementation with ``Fernet`` and ``InvalidToken`` symbols. |
| `stub_httpx` | Lightweight ``httpx`` replacement exposing ``Client``, ``AsyncClient`` and ``HTTPStatusError``. |
| `stub_cachetools` | Simple ``cachetools`` module exporting ``LRUCache``. |
| `stub_settings_facade` | Replacement for ``theo.application.facades.settings`` that returns deterministic defaults. |

The fixtures temporarily override ``sys.modules`` and automatically restore the
original modules after the requesting test completes.  Tests that want to verify
behaviour when a dependency is missing can request the appropriate fixture and
import the module normally.

## Usage patterns

* **Unit-style tests** – Prefer the stub fixtures. For example
  `tests/cli/test_rebuild_embeddings_cmd.py` imports `theo.cli` via the
  ``cli_module`` fixture, which depends on ``stub_sqlalchemy`` and
  ``stub_pythonbible`` so the command helpers can run without a real database.
* **Integration tests** – Import the real modules and guard them with
  ``pytest.importorskip`` when the dependency is optional. The CLI integration
  test continues to exercise SQLite end-to-end with real SQLAlchemy when it is
  installed.

When authoring new tests choose the real integration where feasible.  Fall back
to the stubs only when the dependency is genuinely optional or the test is
exercising failure handling.  This keeps the happy path covered while still
allowing fast smoke tests in lightweight environments.
