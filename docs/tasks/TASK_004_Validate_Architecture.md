# TASK 004: Validate Architecture with Tests

**Priority**: ⭐ LOW (but important)  
**Estimated Time**: 30 minutes  
**Dependencies**: All architecture improvements  
**Status**: Ready to start

---

## 🎯 Objective

Run comprehensive test suite to validate architecture improvements work correctly and catch any integration issues.

---

## 🧪 Test Commands

### 1. Architecture Boundary Tests
```bash
pytest tests/architecture/ -v

# Should verify:
# - No ORM imports in service layer
# - DTOs are immutable
# - Repositories use abstractions
# - No SQLAlchemy in application layer
```

### 2. Repository Unit Tests
```bash
pytest tests/application/repositories/ -v

# Should pass all repository tests with mocks
```

### 3. Integration Tests
```bash
pytest tests/api/routes/test_discoveries_v1.py -v

# Should test v1 routes with new patterns
```

### 4. Full Test Suite
```bash
pytest tests/ -v --tb=short

# Run everything, check for regressions
```

### 5. Coverage Report
```bash
pytest --cov=theo --cov-report=html --cov-report=term

# Verify:
# - New code has >80% coverage
# - No critical paths untested
```

---

## ✅ Success Criteria

- [ ] All architecture tests pass
- [ ] All repository tests pass
- [ ] Integration tests pass
- [ ] No regressions in existing tests
- [ ] Coverage >= 80% for new code
- [ ] Performance tests show improvements

---

## 📝 Actions if Tests Fail

1. **Architecture tests fail**: Fix layer violations immediately
2. **Repository tests fail**: Check mapper implementations
3. **Integration tests fail**: Verify dependency injection
4. **Coverage low**: Add missing test cases

---

**Status**: Validates all previous tasks
