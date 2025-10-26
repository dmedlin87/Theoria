> **Archived on 2025-10-26**

# Test Database Schema Issue - Recurring `perspective` Column Problem

## Problem Summary

Tests repeatedly fail with `sqlite3.OperationalError: no such column: contradiction_seeds.perspective` despite:
- The `perspective` column being defined in `theo/services/api/app/db/models.py` (line 944)
- A migration file existing at `theo/services/api/app/db/migrations/20250129_add_perspective_to_contradiction_seeds.sql`
- Multiple attempts to "fix" this issue

## Root Cause Analysis

### The Test Database Setup Pattern

Tests use **three different database initialization paths**, each with different schema creation mechanisms:

#### 1. **SQLite Tests (Default, 90% of test suite)**
Located in: `tests/conftest.py`
- Creates fresh in-memory SQLite databases via `create_engine("sqlite:///:memory:")`
- Uses `Base.metadata.create_all(engine)` to create schema from SQLAlchemy model definitions
- **Does NOT run SQL migrations by default**
- Expected behavior: Schema should match model definitions exactly

#### 2. **API Integration Tests**
Located in: `tests/api/conftest.py`
- Has an `_disable_migrations` autouse fixture (lines 48-238) that **intentionally disables migrations**
- Creates SQLite databases via `Base.metadata.create_all()` 
- Contains a complex workaround (lines 62-238) to detect and apply the perspective column migration specifically
- This workaround is **fragile** and has multiple fallback paths that can silently fail

#### 3. **PostgreSQL+pgvector Tests (opt-in via `--use-pgvector`)**
Located in: `tests/conftest.py`
- Uses `pgvector_migrated_database_url` fixture which DOES run migrations
- This path works correctly because migrations are applied

### Why the Issue Keeps Recurring

The problem is **Python bytecode caching** combined with **partial test database initialization**:

1. **Stale `.pyc` files**: When model definitions change, cached `.pyc` files in `theo/services/api/app/db/__pycache__/` may contain the OLD model definition without the `perspective` column

2. **Metadata registry caching**: SQLAlchemy's `Base.metadata` is built when modules are first imported. If an old model definition is imported and cached, subsequent calls to `Base.metadata.create_all()` use the stale schema

3. **Test isolation failures**: The `_disable_migrations` fixture in `tests/api/conftest.py` tries to patch multiple import paths (lines 188-199, 228-236) but may miss some import chains, causing tests to use engines created with stale metadata

4. **Silent fallback failures**: The workaround in `tests/api/conftest.py` has multiple exception handlers that silently swallow errors (lines 97, 116, 121, 147, 164), so when the perspective column detection fails, tests proceed with a broken schema

## The Five Files Where Schema Gets Created

| Location | Method | Migrations Run? | Notes |
|----------|--------|-----------------|-------|
| `tests/conftest.py:146` | `_sqlite_database_url` | ❌ No | Base fixture, returns empty DB |
| `tests/conftest.py:165` | `integration_database_url` (postgres) | ✅ Yes | Calls `pgvector_migrated_database_url` |
| `tests/api/conftest.py:247` | `api_engine` fixture | ⚠️ Maybe | Uses `_disable_migrations` workaround |
| `tests/db/test_seeds.py:70` | Direct `create_all` | ❌ No | Fresh in-memory DB per test |
| Individual test files | Varies | ❌ Usually No | Many tests create their own engines |

## Why "Fixing" Doesn't Stick

When an AI agent "fixes" this issue, they typically:
1. ✅ Add the column to the model (already done)
2. ✅ Create a migration file (already done)
3. ❌ **Fail to clear Python cache**
4. ❌ **Fail to restart any running Python processes**
5. ❌ **Fail to fix the fragile workaround in tests/api/conftest.py**

The next test run loads stale cached bytecode, and the problem recurs.

## Permanent Solution

### Short-term (Band-aid)
Clear Python cache before every test run:
```powershell
# In pytest workflow
Remove-Item -Recurse -Force theo\**\__pycache__
Remove-Item -Recurse -Force tests\**\__pycache__
pytest
```

### Medium-term (Proper fix)
Remove the migration-disabling workaround in `tests/api/conftest.py` and ensure ALL test database creation paths run migrations:

1. Modify `tests/conftest.py` to always run migrations for SQLite, not just postgres
2. Remove the 190-line `_disable_migrations` fixture from `tests/api/conftest.py`
3. Accept slightly slower test runs in exchange for schema consistency

### Long-term (Architectural)
Use **Alembic** for proper migration management:
- Alembic generates migrations from model changes
- Alembic has built-in rollback capabilities
- Alembic integrates with pytest-alembic for test fixtures
- Eliminates manual SQL migration files
- Prevents model/schema drift

## Detection Command

Check if cached bytecode is stale:
```powershell
# Find all .pyc files modified before models.py
$modelsTime = (Get-Item theo\services\api\app\db\models.py).LastWriteTime
Get-ChildItem -Recurse -Filter "*.pyc" | Where-Object { $_.LastWriteTime -lt $modelsTime }
```

## Prevention Checklist

Before making ANY schema changes:
- [ ] Clear all `__pycache__` directories
- [ ] Stop any running FastAPI/uvicorn processes
- [ ] Update the SQLAlchemy model
- [ ] Create the SQL migration file
- [ ] Run migration on your local dev database
- [ ] Clear cache again
- [ ] Run full test suite
- [ ] Verify the workaround in `tests/api/conftest.py` still works

## Related Files

- Model definition: `theo/services/api/app/db/models.py:909-953`
- Migration file: `theo/services/api/app/db/migrations/20250129_add_perspective_to_contradiction_seeds.sql`
- Test fixture workaround: `tests/api/conftest.py:48-238`
- Migration runner: `theo/services/api/app/db/run_sql_migrations.py`
- Failing tests: Any test that calls `seed_contradiction_claims()` or instantiates `ContradictionSeed`

## Summary for AI Agents

**DO NOT** attempt to "fix" this issue by:
- Adding the perspective column to the model (already done)
- Creating a migration file (already done)  
- Modifying seed loaders (not the root cause)

**DO** resolve this by:
- Clearing Python bytecode cache: `find . -name "*.pyc" -delete` or equivalent
- Ensuring migrations run in test fixtures
- Considering the architectural solution (Alembic)
