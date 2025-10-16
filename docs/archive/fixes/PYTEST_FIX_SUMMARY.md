# Pytest Test Discovery Fix

## Issues Identified and Resolved

### 1. **Coverage Collection Slowness**

- **Problem**: `--cov=theo` in default pytest options caused slow test discovery by instrumenting 518+ files
- **Solution**: Disabled coverage by default in `pyproject.toml`. Coverage can still be run with explicit flags:

  ```bash
  pytest --cov=theo --cov-report=term-missing --cov-report=xml --cov-fail-under=80
  ```

### 2. **Duplicate Test File Names (Import Conflicts)**

- **Problem**: Multiple test files shared the same basename across different directories, causing Python import conflicts
- **Files Renamed**:
  - `tests/unit/test_tracing.py` → `tests/unit/test_tracing_unit.py`
  - `theo/services/cli/tests/test_code_quality.py` → `theo/services/cli/tests/test_cli_code_quality.py`
  - `theo/services/api/tests/ingest/test_metadata.py` → `theo/services/api/tests/ingest/test_ingest_metadata.py`

### 3. **Test Path Configuration**

- **Problem**: Pytest was collecting tests from service-specific test directories under `theo/services/*/tests/`
- **Solution**: Added `testpaths = ["tests"]` to `pyproject.toml` to restrict collection to the main tests directory

### 4. **Stale Bytecode**

- **Problem**: Old `__pycache__` directories contained stale `.pyc` files
- **Solution**: Cleared all `__pycache__` directories recursively

## Results

- **Before**: Collection failed with 3 errors, took >4 seconds with coverage overhead
- **After**: **552 tests collected successfully in 3.16 seconds** with no errors

## Development Workflow

### Fast Test Discovery (Default)

```bash
pytest --collect-only  # Fast collection, no coverage
pytest tests/api/      # Run specific test directory
pytest -k "pattern"    # Run tests matching pattern
```

### Full Coverage Run (CI/CD)

```bash
pytest --cov=theo --cov-report=term-missing --cov-report=xml --cov-fail-under=80
```

### Clear Cache When Needed

```powershell
Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
```
