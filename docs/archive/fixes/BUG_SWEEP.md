# Bug Sweep Report

## Overview
A repository-wide test sweep was executed with `pytest`. Collection failed due to four distinct issues, preventing the suite from running to completion. Additional targeted imports reproduced the underlying problems. Each failure is documented below with reproduction guidance and suspected root causes.

## 1. Circular import in RAG workflow exports
- **Symptom:** Importing `theo.services.api.app.ai.rag` fails during API test collection with `ImportError: cannot import name 'build_sermon_deliverable' from partially initialized module`.
- **Reproduction:** `pytest` or `python -c "import theo.services.api.app.ai.rag"` while the API app loads workers.
- **Cause:** `IngestionService` depends on the CLI ingest module, which in turn imports Celery workers. The worker module re-imports the RAG package, creating a cycle before `build_sermon_deliverable` is defined.
- **Relevant files:**
  - `theo/services/api/app/infra/ingestion_service.py` imports the CLI ingest entry point. 【F:theo/services/api/app/infra/ingestion_service.py†L1-L60】
  - `theo/services/cli/ingest_folder.py` pulls in worker tasks, tying the API import path back to Celery. 【F:theo/services/cli/ingest_folder.py†L1-L40】
  - `theo/services/api/app/workers/tasks.py` imports `build_sermon_deliverable` from the RAG package, closing the circular chain. 【F:theo/services/api/app/workers/tasks.py†L1-L28】
- **Captured error:** `ImportError` during `pytest` collection. 【4271a6†L4-L35】

## 2. Schemathesis experimental API removal
- **Symptom:** Contract tests fail to import `experimental` from Schemathesis.
- **Reproduction:** `pytest tests/contracts/test_schemathesis.py`.
- **Cause:** The test suite imports `schemathesis.experimental`, which was removed in Schemathesis 4.x; the currently installed version exposes no such attribute.
- **Relevant file:** `tests/contracts/test_schemathesis.py` still references the deprecated module. 【F:tests/contracts/test_schemathesis.py†L1-L35】
- **Captured error:** `ImportError: cannot import name 'experimental' from 'schemathesis'`. 【4271a6†L35-L47】

## 3. Circular bootstrap dependency in CLI helpers
- **Symptom:** Importing `theo.services.cli.code_quality` or running the CLI tests triggers `ImportError: cannot import name 'resolve_application' ... (circular import)`.
- **Reproduction:** `python -c "import importlib; importlib.import_module('theo.services.cli.tests.test_code_quality')"`.
- **Cause:** `code_quality.py` imports `resolve_application`, which imports `theo.application.facades`. The facades package re-imports `resolve_application` via its `research` facade, causing a bootstrap-time cycle.
- **Relevant files:**
  - `theo/services/cli/code_quality.py` imports `resolve_application`. 【F:theo/services/cli/code_quality.py†L1-L80】
  - `theo/application/services/bootstrap.py` loads application facades during initialization and is re-exported by `theo/services/bootstrap`. 【F:theo/application/services/bootstrap.py†L1-L40】
  - `theo/application/facades/__init__.py` re-exports the research facade, which calls back into `resolve_application`. 【F:theo/application/facades/__init__.py†L1-L52】
  - `theo/application/facades/research.py` invokes `resolve_application`, completing the loop. 【F:theo/application/facades/research.py†L1-L32】
- **Captured error:** Circular import trace when importing the CLI test module. 【fe7ee2†L1-L21】

## 4. Missing pytest-cov dependency
- **Symptom:** Invoking pytest with default configuration flags (`--cov=...`) fails because the coverage plugin is unavailable.
- **Reproduction:** `pytest theo/services/cli/tests/test_code_quality.py -vv`.
- **Cause:** The project configures pytest to run with `pytest-cov`, but the plugin is not present in the environment despite being listed in `requirements-dev.txt`.
- **Captured error:** `pytest: error: unrecognized arguments: --cov=...`. 【0ca248†L1-L4】
- **Dependency manifest:** `pytest-cov` is declared as a dev dependency. 【F:requirements-dev.txt†L1-L20】

## Test Command Log
- Primary run: `pytest` (fails during collection). 【4271a6†L1-L61】
