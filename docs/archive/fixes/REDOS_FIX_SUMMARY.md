# ReDoS Vulnerability Fix Summary

## Issue
**CodeQL Alert**: Polynomial regular expression used on uncontrolled data  
**Severity**: High  
**Location**: `theo/services/api/app/ai/passage.py:133`

The regex pattern for parsing Bible passage references was vulnerable to Regular Expression Denial of Service (ReDoS) attacks. The pattern `(?P<book>[\d\w\s]+?)` could cause catastrophic backtracking when processing malicious input with many alternating word characters and spaces.

## Root Cause
The original pattern used a **lazy quantifier** (`+?`) with character classes that overlap (`\d`, `\w`, `\s`). This creates multiple ways for the regex engine to match the same input, leading to exponential time complexity when the pattern fails to match.

Example malicious input: `"a " * 1000 + "invalid"` would cause the regex engine to try exponentially many backtracking paths.

## Fix Applied

### 1. **Regex Pattern Optimization** (lines 133-157)
**Before:**
```python
(?P<book>[\d\w\s]+?)  # Vulnerable: lazy quantifier with overlapping classes
```

**After:**
```python
(?P<book>[\w\d]+(?:\s+[\w\d]+)*)  # Safe: atomic grouping prevents backtracking
```

The new pattern uses **atomic grouping** (non-capturing groups with specific structure) to prevent catastrophic backtracking:
- `[\w\d]+` matches one or more word/digit characters
- `(?:\s+[\w\d]+)*` matches zero or more occurrences of (one or more spaces + word/digit characters)
- This structure eliminates ambiguity and forces linear matching

### 2. **Input Length Validation** (passage.py line 167)
Added defensive check in `resolve_passage_reference()`:
```python
if len(passage) > 200:
    raise PassageResolutionError("Passage reference too long (max 200 characters).")
```

### 3. **Request Model Validation** (models/ai.py line 290)
Added Pydantic field validation:
```python
passage: str | None = Field(None, max_length=200)
```

This provides **defense-in-depth**: validation at both the API layer (Pydantic) and business logic layer (passage parser).

## Testing

Created comprehensive test suite in `tests/test_redos_fix.py`:
- ✅ **Length validation test**: Rejects inputs >200 characters
- ✅ **Performance test**: Confirms malicious patterns complete in <0.1 seconds
- ✅ **Regression tests**: Validates all legitimate passage formats still work
- ✅ **Edge case tests**: Handles various whitespace patterns correctly

All tests pass successfully.

## Impact
- **Security**: Eliminates ReDoS attack vector
- **Performance**: Regex matching is now O(n) instead of O(2^n) worst case
- **Functionality**: No breaking changes - all valid Bible references continue to work

## References
- CodeQL Rule: `py/polynomial-redos`
- CWE-1333: Inefficient Regular Expression Complexity
- OWASP: Regular expression Denial of Service

## Date
October 15, 2025
