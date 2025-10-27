# Memory Leak Review - TheoEngine

**Review Date:** October 12, 2025  
**Reviewer:** Cascade AI  
**Scope:** Python backend (FastAPI + Celery) and Next.js frontend

---

## Executive Summary

The codebase demonstrates **generally good memory management practices** with proper cleanup in most areas. However, **several potential memory leaks were identified** that should be addressed, primarily around HTTP client lifecycle management and unbounded cache growth.

### Risk Level: **MODERATE**

**Critical Issues:** 1  
**High Priority:** 2  
**Medium Priority:** 3  
**Low Priority:** 2

---

## Critical Issues

### 1. ❌ **HTTP Clients Not Closed in AI Client Wrappers**

**Location:** `theo/services/api/app/ai/clients.py`

**Issue:** All AI client classes (`OpenAIClient`, `AzureOpenAIClient`, `AnthropicClient`, `VertexAIClient`, `LocalVLLMClient`) create `httpx.Client` instances but **never close them**. HTTP clients maintain connection pools that must be explicitly closed.

**Current Code:**

```python
class OpenAIClient(BaseAIClient):
    def __init__(self, config: OpenAIConfig, *, settings: AIClientSettings | None = None):
        # ...
        client = BaseAIClient._create_http_client(
            base_url=config.base_url,
            headers=headers,
            settings=resolved_settings,
        )
        super().__init__(client, resolved_settings)
        # NO CLOSE METHOD OR CONTEXT MANAGER SUPPORT
```

**Impact:**

- Connection pool exhaustion over time
- Socket descriptors remain open
- Memory consumption from connection buffers

**Recommendation:**

```python
class BaseAIClient:
    def close(self) -> None:
        """Close the underlying HTTP client."""
        if hasattr(self, '_client') and self._client is not None:
            self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

# Usage in workers/routes:
with OpenAIClient(config) as client:
    result = client.generate(...)
```

**Note:** `OpenAlexClient` correctly implements a `close()` method but it's not consistently used.

---

## High Priority Issues

### 2. ⚠️ **Unbounded Cache Growth in AI Clients**

**Location:** `theo/services/api/app/ai/clients.py` (line 176)

**Issue:** All AI client classes use an unbounded in-memory cache (`self._cache: dict[str, str] = {}`) that grows indefinitely with every unique `cache_key`.

**Current Code:**

```python
class BaseAIClient:
    def __init__(self, http_client: httpx.Client, settings: AIClientSettings | None = None):
        self._cache: dict[str, str] = {}  # NO SIZE LIMIT
```

**Impact:**

- Memory grows linearly with unique prompts
- In long-running Celery workers, this can cause OOM errors
- No eviction policy for stale entries

**Recommendation:**
Use `functools.lru_cache` or `cachetools.LRUCache`:

```python
from cachetools import LRUCache

class BaseAIClient:
    def __init__(self, http_client: httpx.Client, settings: AIClientSettings | None = None):
        self._cache: LRUCache = LRUCache(maxsize=256)  # Configurable limit
```

### 3. ⚠️ **SQLite NullPool May Cause Connection Buildup**

**Location:** `theo/application/facades/database.py` (lines 30-31)

**Issue:** SQLite connections use `NullPool`, which creates a new connection for every request and relies on garbage collection for cleanup. If sessions aren't explicitly closed, connections accumulate.

**Current Code:**

```python
if database_url.startswith("sqlite"):
    engine_kwargs["poolclass"] = NullPool
```

**Observed Pattern:**
✅ Most code properly uses `with Session(engine) as session:` context managers  
✅ FastAPI dependency `get_session()` has proper try/finally cleanup  
⚠️ Some test code creates sessions without context managers

**Recommendation:**

- Audit all `Session(engine)` calls to ensure they use context managers
- Consider using `StaticPool` for SQLite in tests for deterministic cleanup
- Add a test to detect unclosed sessions:

```python
# Add to conftest.py
@pytest.fixture(autouse=True)
def check_session_leaks():
    initial_count = len(gc.get_objects())
    yield
    gc.collect()
    final_count = len(gc.get_objects())
    assert final_count - initial_count < 100, "Potential session leak"
```

---

## Medium Priority Issues

### 4. 🔶 **Celery Task Engine References Retained**

**Location:** `theo/services/api/app/workers/tasks.py`

**Issue:** Tasks call `get_engine()` which creates/reuses a global engine singleton, but individual sessions are properly managed. The engine itself is never explicitly disposed during worker shutdown.

**Current Pattern:**

```python
@celery.task(name="tasks.process_file")
def process_file(...):
    engine = get_engine()  # Global singleton
    with Session(engine) as session:  # ✅ Properly scoped
        # work...
```

**Recommendation:**
Add Celery worker lifecycle hooks:

```python
from celery.signals import worker_shutdown

@worker_shutdown.connect
def cleanup_engine(sender, **kwargs):
    from theo.application.facades.database import _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None
```

### 5. 🔶 **File Handles in Tests Use Context Managers Inconsistently**

**Location:** Various test files

**Issue:** Most file operations use `with` statements correctly, but some tests open files without explicit cleanup:

**Examples:**

- `tests/test_ingest_and_search.py` line 290: `with pdf_path.open("rb") as handle:` ✅
- `app/db/seeds.py` line 43: `with path.open("r", encoding="utf-8") as handle:` ✅
- All usages reviewed appear correct

**Status:** ✅ No issues found in file handle management

### 6. 🔶 **URL Opener Not Explicitly Closed**

**Location:** `theo/services/api/app/ingest/network.py` (line 212)

**Issue:** `urllib.request.build_opener()` creates an opener that holds references, though CPython's garbage collector should handle it.

**Current Code:**

```python
opener = opener_factory(redirect_handler)
response = opener.open(request, timeout=timeout)
# No explicit opener cleanup
```

**Impact:** Low - Python's GC handles this, but explicit cleanup is better practice

**Recommendation:**

```python
finally:
    if hasattr(opener, 'close'):
        opener.close()
```

---

## Low Priority Issues

### 7. ✅ **React useEffect Cleanup - WELL IMPLEMENTED**

**Review:** All React components properly implement cleanup functions for:

- ✅ Event listeners (`addEventListener` + `removeEventListener`)
- ✅ Timers (`setTimeout` + `clearTimeout`, `setInterval` + `clearInterval`)
- ✅ WebSocket connections (`websocket.close()`)
- ✅ AbortControllers (`controller.abort()`)
- ✅ Media queries (`mediaQuery.removeEventListener`)

**Example from `NotebookRealtimeListener.tsx`:**

```typescript
useEffect(() => {
  const websocket = new WebSocket(buildRealtimeUrl(notebookId));
  // ...
  return () => {
    websocket.close();  // ✅ Proper cleanup
    wsRef.current = null;
  };
}, [notebookId]);
```

**Status:** No issues found in React cleanup patterns.

### 8. ✅ **Database Session Management - MOSTLY CORRECT**

**Review:** The codebase consistently uses proper session management:

- ✅ FastAPI dependency injection with try/finally
- ✅ Context managers in Celery tasks: `with Session(engine) as session:`
- ✅ Explicit `session.close()` in the `get_session()` generator
- ✅ Session factory configured with `autocommit=False` and `expire_on_commit=False`

**Potential Issue:** Session factory uses `expire_on_commit=False` which keeps objects in memory after commit. This is intentional for the application design but worth noting.

---

## Recommendations Summary

### Immediate Actions (Critical/High Priority)

1. **Add `close()` method and context manager support to all AI clients**

   ```python
   # Add to BaseAIClient and all subclasses
   def __enter__(self): return self
   def __exit__(self, *args): self.close()
   def close(self): self._client.close()
   ```

2. **Replace unbounded cache with LRU cache**

   ```bash
   pip install cachetools
   ```

   Update `BaseAIClient.__init__` to use `LRUCache(maxsize=256)`

3. **Audit all Session() instantiations**

   ```bash
   # Search for sessions not using context managers
   rg "Session\(" --type py | grep -v "with Session"
   ```

### Medium-Term Improvements

1. **Add Celery worker shutdown hooks** for engine disposal
2. **Add session leak detection to test suite** using pytest fixtures
3. **Explicitly close urllib openers** in `network.py`

### Monitoring Recommendations

1. **Add Prometheus metrics for:**
   - Active database sessions: `sqlalchemy_active_sessions`
   - HTTP client pool usage: `httpx_pool_connections`
   - Cache size: `ai_client_cache_size`

2. **Enable SQLAlchemy pool logging in staging:**

   ```python
   import logging
   logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)
   ```

---

## Testing Strategy

### 1. Memory Profiler Tests

```python
import tracemalloc

def test_ai_client_memory_leak():
    tracemalloc.start()
    
    client = OpenAIClient(config)
    for i in range(1000):
        client.generate(prompt=f"test {i}", model="gpt-4")
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    # Should not exceed 10MB for 1000 cached responses
    assert current < 10 * 1024 * 1024
```

### 2. Connection Pool Exhaustion Test

```python
def test_http_client_pool_cleanup():
    clients = []
    for _ in range(100):
        client = OpenAIClient(config)
        clients.append(client)
    
    # Without proper cleanup, this would exhaust file descriptors
    for client in clients:
        client.close()  # Verify this exists and works
```

### 3. Long-Running Celery Task Test

```bash
# Run a worker for 24 hours with monitoring
celery -A theo.infrastructure.api.app.workers worker --loglevel=info &
CELERY_PID=$!

# Monitor memory over time
while kill -0 $CELERY_PID 2>/dev/null; do
    ps -p $CELERY_PID -o rss,vsz
    sleep 3600
done
```

---

## Code Quality Observations

### ✅ **Strengths**

1. **Consistent use of context managers** for database sessions
2. **Proper React cleanup patterns** throughout the frontend
3. **Good use of try/finally blocks** for resource cleanup
4. **SQLAlchemy engine properly configured** with connection pooling
5. **FastAPI lifespan events** properly handle startup/shutdown

### ⚠️ **Areas for Improvement**

1. HTTP client lifecycle management
2. Cache size limits
3. Worker shutdown hooks
4. Memory profiling in CI/CD

---

## Conclusion

The TheoEngine codebase demonstrates **solid engineering practices** with minimal memory leak risks. The identified issues are **straightforward to fix** and primarily involve:

1. Adding explicit resource cleanup to HTTP clients
2. Implementing cache size limits
3. Adding observability for long-running processes

**Priority:** Address issues #1 and #2 before deploying to production with long-running Celery workers.

**Estimated Effort:** 4-6 hours for all critical and high-priority fixes.

---

## Next Steps

1. [ ] Create GitHub issues for each critical/high priority item
2. [ ] Add `close()` methods to AI clients
3. [ ] Replace unbounded caches with LRU caches
4. [ ] Add memory profiling to CI pipeline
5. [ ] Set up Prometheus metrics for resource tracking
6. [ ] Schedule code review for session management patterns

---

**Report Generated:** 2025-10-12  
**Tool:** Cascade AI Memory Leak Analysis  
**Confidence Level:** High (based on comprehensive code review)
