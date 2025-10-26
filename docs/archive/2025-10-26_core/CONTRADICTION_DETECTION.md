> **Archived on 2025-10-26**

# Contradiction Detection - Implementation Summary

## Overview

Contradiction detection is now fully implemented using Natural Language Inference (NLI) to automatically identify conflicting claims between documents in a user's corpus.

## How It Works

### 1. NLI Model
- **Model:** microsoft/deberta-v3-base-mnli (~400MB)
- **Task:** Classify text pairs as entailment/neutral/contradiction
- **Threshold:** 0.7 (configurable)
- **Min Confidence:** 0.6 (configurable)

### 2. Detection Process

```
1. Extract claims from documents (abstract or title)
   ↓
2. Compare all document pairs using NLI
   ↓
3. Filter for contradiction score >= 0.7
   ↓
4. Create discovery with confidence and metadata
   ↓
5. Persist to database as CONTRADICTION type
   ↓
6. Display in /discoveries feed
```

### 3. Contradiction Types

Automatically inferred from shared topics:

- **Theological** - Christology, soteriology, ecclesiology, etc.
- **Historical** - Chronology, dates, events
- **Textual** - Manuscripts, variants, translations
- **Logical** - Default for other contradictions

## Files Created

### Core Engine
- `theo/domain/discoveries/contradiction_engine.py` - Main detection logic
- `tests/domain/discoveries/test_contradiction_engine.py` - Unit tests

### Integration
- Modified `theo/domain/discoveries/__init__.py` - Export engine
- Modified `theo/services/api/app/discoveries/service.py` - Integrate into refresh

### Dependencies
- Added to `requirements.txt`:
  - `transformers>=4.30,<5`
  - `torch>=2.0,<3`
  - `sentencepiece>=0.1.99,<0.2`

## Usage

### Automatic Detection

Contradictions are automatically detected:
- After every document upload (background task)
- Every 30 minutes (periodic scheduler)

### Manual Trigger

```python
from theo.services.api.app.discoveries import DiscoveryService
from theo.application.facades.database import get_session
from theo.adapters.persistence.discovery_repository import SQLAlchemyDiscoveryRepository
from theo.adapters.persistence.document_repository import SQLAlchemyDocumentRepository

    with get_session() as session:
        discovery_repo = SQLAlchemyDiscoveryRepository(session)
        document_repo = SQLAlchemyDocumentRepository(session)
        service = DiscoveryService(discovery_repo, document_repo)
    discoveries = service.refresh_user_discoveries(user_id="abc123")
    
    # Filter for contradictions
    contradictions = [d for d in discoveries if d.discovery_type == "contradiction"]
    print(f"Found {len(contradictions)} contradictions")
```

### API Access

```bash
# Get all discoveries (includes contradictions)
GET /api/discoveries

# Filter for contradictions only
GET /api/discoveries?discovery_type=contradiction

# Mark as viewed
POST /api/discoveries/{id}/view

# Provide feedback
POST /api/discoveries/{id}/feedback
{
  "helpful": true
}

# Dismiss
DELETE /api/discoveries/{id}
```

## Example Output

```json
{
  "id": 123,
  "type": "contradiction",
  "title": "Contradiction detected: Jesus is Fully Divine vs Jesus is Subordinate",
  "description": "These documents appear to contradict each other. Jesus is Fully Divine states one position, while Jesus is Subordinate takes a conflicting stance. Shared topics: christology, theology.",
  "confidence": 0.85,
  "relevance_score": 0.7,
  "viewed": false,
  "created_at": "2025-01-15T21:00:00Z",
  "metadata": {
    "document_a_id": "doc1",
    "document_b_id": "doc2",
    "document_a_title": "Jesus is Fully Divine",
    "document_b_title": "Jesus is Subordinate to the Father",
    "claim_a": "This document argues that Jesus Christ is fully divine...",
    "claim_b": "This document argues that Jesus is subordinate to God...",
    "contradiction_type": "theological",
    "nli_scores": {
      "contradiction": 0.85,
      "neutral": 0.10,
      "entailment": 0.05
    },
    "shared_topics": ["christology", "theology"]
  }
}
```

## Configuration

### Environment Variables

```bash
# NLI model to use (default: microsoft/deberta-v3-base-mnli)
THEORIA_NLI_MODEL=microsoft/deberta-v3-base-mnli

# Contradiction threshold (default: 0.7)
THEORIA_CONTRADICTION_THRESHOLD=0.7

# Minimum confidence to include (default: 0.6)
THEORIA_MIN_CONTRADICTION_CONFIDENCE=0.6
```

### Code Configuration

```python
from theo.domain.discoveries import ContradictionDiscoveryEngine

# Custom configuration
engine = ContradictionDiscoveryEngine(
    model_name="custom-nli-model",
    contradiction_threshold=0.8,  # Stricter
    min_confidence=0.5,  # More permissive
)
```

## Performance

### First Run
- Downloads model (~400MB) - one-time cost
- Caches model in `~/.cache/huggingface/`

### Subsequent Runs
- Model loaded from cache
- Inference: ~50-100ms per pair
- For 100 documents: ~5000 pairs = ~8-15 seconds

### Optimization Tips

1. **Batch Processing** - Compare documents in batches
2. **Caching** - Cache NLI results for document pairs
3. **Sampling** - For large corpora (1000+ docs), sample representative pairs
4. **GPU** - Use GPU if available for 10x speedup

## Testing

### Run Unit Tests

```bash
# All tests
pytest tests/domain/discoveries/test_contradiction_engine.py -v

# Skip slow tests (require model download)
pytest tests/domain/discoveries/test_contradiction_engine.py -v -m "not slow"

# Run slow tests (downloads model)
pytest tests/domain/discoveries/test_contradiction_engine.py -v -m slow
```

### Manual Testing

1. **Upload contradictory documents:**
   ```bash
   # Upload document arguing Jesus is divine
   curl -X POST http://localhost:8000/api/ingest/file \
     -F "file=@divine.pdf" \
     -H "Authorization: Bearer $TOKEN"
   
   # Upload document arguing Jesus is subordinate
   curl -X POST http://localhost:8000/api/ingest/file \
     -F "file=@subordinate.pdf" \
     -H "Authorization: Bearer $TOKEN"
   ```

2. **Wait for background task** (~30 seconds)

3. **Check discoveries:**
   ```bash
   curl http://localhost:8000/api/discoveries?discovery_type=contradiction \
     -H "Authorization: Bearer $TOKEN"
   ```

## Troubleshooting

### Model Download Fails

**Symptom:** `ConnectionError` or `HTTPError` during first run

**Solution:**
```bash
# Pre-download model
python -c "from transformers import AutoModel; AutoModel.from_pretrained('microsoft/deberta-v3-base-mnli')"
```

### Out of Memory

**Symptom:** `RuntimeError: CUDA out of memory` or system freeze

**Solution:**
- Reduce batch size
- Use CPU instead of GPU
- Increase system RAM
- Sample document pairs instead of all pairs

### No Contradictions Found

**Symptom:** `refresh_user_discoveries()` returns 0 contradictions

**Causes:**
- Less than 2 documents in corpus
- Documents don't have abstracts/titles
- No actual contradictions exist
- Threshold too high

**Solution:**
```python
# Lower threshold for testing
engine = ContradictionDiscoveryEngine(
    contradiction_threshold=0.5,  # Lower
    min_confidence=0.4,  # Lower
)
```

### Slow Performance

**Symptom:** Discovery refresh takes > 60 seconds

**Solution:**
- Enable GPU if available
- Cache NLI results
- Limit to top N document pairs by relevance
- Run async in background

## Future Enhancements

### Short-term
- **Claim extraction** - Use dedicated claim extraction models instead of abstracts
- **Caching** - Cache NLI results for document pairs
- **Batch inference** - Process multiple pairs in parallel

### Medium-term
- **Link to existing seeds** - Connect to `data/seeds/contradictions.json`
- **Explanation generation** - Use LLM to explain why contradiction exists
- **Resolution suggestions** - Suggest how to resolve the contradiction

### Long-term
- **Fine-tuned NLI** - Train on theological texts for better accuracy
- **Multi-document contradictions** - Detect contradictions across 3+ documents
- **Contradiction graphs** - Visualize contradiction networks

## Related Documentation

- [DISCOVERY_FEATURE.md](DISCOVERY_FEATURE.md) - Complete discovery feature spec
- [DISCOVERY_SCHEDULER.md](DISCOVERY_SCHEDULER.md) - Background scheduler
- [AGENT_AND_PROMPTING_GUIDE.md](AGENT_AND_PROMPTING_GUIDE.md) - Agent architecture
- [HANDOFF_NEXT_PHASE.md](../HANDOFF_NEXT_PHASE.md) - Next development phases

---

**Status:** ✅ Complete and integrated  
**Last Updated:** 2025-01-15  
**Next:** Gap Analysis (Phase 1.2)
