# TASK 003: Add Query Optimizations to Existing Endpoints

**Priority**: ⭐⭐ MEDIUM  
**Estimated Time**: 1-2 hours  
**Dependencies**: Query optimization tools (✅ Done)  
**Status**: Ready to start

---

## 🎯 Objective

Add eager loading and performance monitoring to high-traffic endpoints to eliminate N+1 queries and improve response times.

---

## 📊 Target Endpoints

### 1. Search Endpoint
**File**: `theo/infrastructure/api/app/routes/search.py`

**Current Issue**: N+1 queries loading documents + passages

**Fix**:
```python
from sqlalchemy.orm import selectinload
from ..db.query_optimizations import query_with_monitoring

@query_with_monitoring("search.hybrid_search")
def hybrid_search(...):
    stmt = (
        select(Document)
        .options(selectinload(Document.passages))
        .where(...)
    )
    return session.scalars(stmt).all()
```

### 2. Document Detail Endpoint
**File**: `theo/infrastructure/api/app/routes/documents.py`

**Fix**: Eager load passages when retrieving single document

### 3. Discovery Listing
**File**: `theo/infrastructure/api/app/routes/discoveries.py`

**Fix**: Add pagination, limit to 100 per page

---

## 🧪 Testing

Before/after performance measurement:

```python
import time

# Measure query count and time
start = time.perf_counter()
result = endpoint_function()
duration = time.perf_counter() - start

print(f"Duration: {duration:.3f}s")
print(f"Result count: {len(result)}")
```

---

## ✅ Success Criteria

- [ ] Search endpoint: 2 queries instead of 1+N
- [ ] Document detail: 1-2 queries instead of 1+N
- [ ] Monitoring decorators added
- [ ] Performance metrics show improvement
- [ ] No breaking changes to API responses

---

**Next Task**: TASK_004 (Architecture Validation)
