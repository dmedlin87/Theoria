# LangChain Text Splitters Security Advisory

## Issue
Dependabot alert #8 for CVE-611: LangChain Text Splitters vulnerable to XML External Entity (XXE) attacks

## Current Status
- **Vulnerable version installed**: `langchain-text-splitters==0.2.4`
- **Fixed in**: `langchain-text-splitters>=0.3.13` (not yet published; latest is 0.3.11 or 1.0.0a1)
- **Transitive dependency from**: `langchain==0.2.17` and `langchain-community==0.2.19`

## Why Not Fixed Yet
1. **Incompatible versions**: Upgrading to `langchain-text-splitters>=0.3.11` requires:
   - `langchain-core>=1.0.0` (currently locked at `0.2.43`)
   - `langsmith>=0.3.45` (currently locked at `0.1.147`)
   - Breaking changes across the entire LangChain ecosystem

2. **Limited exposure**: We only use LangChain for:
   - `FakeListChatModel` (test fixtures in `theo/services/cli/rag_eval.py`)
   - `FakeEmbeddings` (test fixtures in `theo/services/cli/rag_eval.py`)
   - **Not using the vulnerable `SectionGetSplitter` class**

3. **Version constraints**: `ragas==0.1.22` requires `langchain-core<0.3`

## Mitigation Plan
1. **Short term**: Accept risk (low exposure, test-only usage, no XSLT parsing in our code)
2. **Medium term**: Monitor for:
   - `ragas` update supporting `langchain-core>=1.0`
   - `langchain-text-splitters>=0.3.13` official release
3. **Long term**: Upgrade entire LangChain stack once dependencies align

## Next Actions
- [ ] Watch for `ragas` compatibility updates
- [ ] Test with `langchain==0.3.x` once `ragas` supports it
- [ ] Consider removing LangChain dependency entirely if only used for test fakes

## Date
October 15, 2025
