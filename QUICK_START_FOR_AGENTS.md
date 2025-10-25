# Quick Start Guide for AI Agents

This is a condensed guide for AI agents picking up development. Read this first, then refer to detailed docs as needed.

---

## What You Need to Know

### Project Status
- **Working:** Frontend UI, RAG pipeline, pattern detection, contradiction detection, background scheduler
- **TODO:** 4 more discovery types, agent reasoning UI, dashboard, citations

### Your Mission
Complete the discovery engine by implementing 4 remaining discovery types, then expose agent reasoning in UI.

---

## Next Task: Gap Analysis (Phase 1.2)

### Goal
Detect missing topics in user's corpus by comparing against reference theological topics.

### Implementation Steps

**1. Create the engine:**
```python
# File: theo/domain/discoveries/gap_engine.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence
from bertopic import BERTopic
from .models import DocumentEmbedding

@dataclass(frozen=True)
class GapDiscovery:
    title: str
    description: str
    missing_topic: str
    confidence: float
    relevance_score: float
    suggested_searches: list[str]
    metadata: dict[str, object]

class GapDiscoveryEngine:
    def __init__(self):
        self.topic_model = BERTopic()
        self.reference_topics = self._load_reference_topics()
    
    def _load_reference_topics(self) -> set[str]:
        # Load from data/seeds/theological_topics.yaml
        # Return set of standard topics
        pass
    
    def detect(self, documents: Sequence[DocumentEmbedding]) -> list[GapDiscovery]:
        if len(documents) < 20:  # Need minimum corpus
            return []
        
        # 1. Extract topics from user corpus
        texts = [doc.abstract or doc.title for doc in documents]
        topics, _ = self.topic_model.fit_transform(texts)
        user_topics = set(self.topic_model.get_topic_info()['Name'])
        
        # 2. Find missing topics
        missing = self.reference_topics - user_topics
        
        # 3. Create discoveries
        discoveries = []
        for topic in missing:
            discoveries.append(GapDiscovery(
                title=f"Gap detected: {topic}",
                description=f"Your corpus lacks coverage of {topic}. Consider adding resources on this topic.",
                missing_topic=topic,
                confidence=0.8,
                relevance_score=self._calculate_relevance(topic, user_topics),
                suggested_searches=[f"{topic} theology", f"biblical {topic}"],
                metadata={"user_topics": list(user_topics), "missing_topics": list(missing)}
            ))
        
        return discoveries[:20]  # Limit results
```

**2. Create reference topics:**
```yaml
# File: data/seeds/theological_topics.yaml

systematic_theology:
  - Theology Proper
  - Christology
  - Pneumatology
  - Soteriology
  - Ecclesiology
  - Eschatology
  - Anthropology
  - Hamartiology

biblical_theology:
  - Covenant Theology
  - Kingdom of God
  - Redemptive History
  - Biblical Typology

historical_theology:
  - Early Church Fathers
  - Medieval Theology
  - Reformation Theology
  - Modern Theology

practical_theology:
  - Worship
  - Preaching
  - Pastoral Care
  - Spiritual Formation
```

**3. Write tests:**
```python
# File: tests/domain/discoveries/test_gap_engine.py

import pytest
from theo.domain.discoveries.gap_engine import GapDiscoveryEngine, GapDiscovery
from theo.domain.discoveries.models import DocumentEmbedding

def test_gap_engine_requires_minimum_documents():
    engine = GapDiscoveryEngine()
    discoveries = engine.detect([])  # Too few
    assert discoveries == []

def test_gap_detection_finds_missing_topics():
    engine = GapDiscoveryEngine()
    # Create documents covering only Christology
    docs = [create_doc("Christology") for _ in range(25)]
    
    discoveries = engine.detect(docs)
    
    # Should find gaps in other topics
    assert len(discoveries) > 0
    missing_topics = [d.missing_topic for d in discoveries]
    assert "Soteriology" in missing_topics
```

**4. Integrate into service:**
```python
# File: theo/services/api/app/discoveries/service.py

from theo.domain.discoveries import (
    ContradictionDiscoveryEngine,
    GapDiscoveryEngine,  # Add this
    DiscoveryType,
    DocumentEmbedding,
    PatternDiscoveryEngine,
)

class DiscoveryService:
    def __init__(
        self,
        session: Session,
        pattern_engine: PatternDiscoveryEngine | None = None,
        contradiction_engine: ContradictionDiscoveryEngine | None = None,
        gap_engine: GapDiscoveryEngine | None = None,  # Add this
    ):
        self.session = session
        self.pattern_engine = pattern_engine or PatternDiscoveryEngine()
        self.contradiction_engine = contradiction_engine or ContradictionDiscoveryEngine()
        self.gap_engine = gap_engine or GapDiscoveryEngine()  # Add this
    
    def refresh_user_discoveries(self, user_id: str) -> list[Discovery]:
        documents = self._load_document_embeddings(user_id)
        
        # Run all engines
        pattern_candidates, snapshot = self.pattern_engine.detect(documents)
        contradiction_candidates = self.contradiction_engine.detect(documents)
        gap_candidates = self.gap_engine.detect(documents)  # Add this
        
        # Delete old discoveries
        self.session.execute(
            delete(Discovery).where(
                Discovery.user_id == user_id,
                Discovery.discovery_type.in_([
                    DiscoveryType.PATTERN.value,
                    DiscoveryType.CONTRADICTION.value,
                    DiscoveryType.GAP.value,  # Add this
                ]),
            )
        )
        
        # Persist gap discoveries
        for candidate in gap_candidates:
            record = Discovery(
                user_id=user_id,
                discovery_type=DiscoveryType.GAP.value,
                title=candidate.title,
                description=candidate.description,
                confidence=float(candidate.confidence),
                relevance_score=float(candidate.relevance_score),
                viewed=False,
                meta={
                    "missing_topic": candidate.missing_topic,
                    "suggested_searches": candidate.suggested_searches,
                    **candidate.metadata,
                },
                created_at=datetime.now(UTC),
            )
            self.session.add(record)
        
        # ... rest of method
```

**5. Add dependency:**
```txt
# File: requirements.txt
# Add this line:
bertopic>=0.15,<1
```

**6. Export from module:**
```python
# File: theo/domain/discoveries/__init__.py

from .gap_engine import GapDiscovery, GapDiscoveryEngine  # Add this

__all__ = [
    "ContradictionDiscovery",
    "ContradictionDiscoveryEngine",
    "GapDiscovery",  # Add this
    "GapDiscoveryEngine",  # Add this
    # ... rest
]
```

---

## Testing Your Work

```bash
# 1. Install dependency
pip install bertopic

# 2. Run unit tests
pytest tests/domain/discoveries/test_gap_engine.py -v

# 3. Run integration test
pytest tests/api/test_discovery_integration.py -v

# 4. Manual test
# Start services
.\start-theoria.ps1

# Upload 20+ documents
# Wait 30s for background task
# Check discoveries
curl http://localhost:8000/api/discoveries?type=gap
```

---

## After Gap Analysis

Continue with remaining discovery types in order:

1. **Connection Detection** (graph-based, shared verses)
2. **Trend Detection** (time-series, requires 3+ snapshots)
3. **Anomaly Detection** (isolation forest, outliers)

Then move to Phase 2: Expose Agent Reasoning in UI.

---

## Key Files to Reference

- `theo/domain/discoveries/contradiction_engine.py` - Just implemented, good example
- `theo/domain/discoveries/engine.py` - Pattern detection, another example
- `theo/services/api/app/discoveries/service.py` - Integration point
- `IMPLEMENTATION_CONTEXT.md` - Detailed patterns and conventions
- `HANDOFF_NEXT_PHASE.md` - Full roadmap

---

## Getting Help

All context is in the documentation:
- Architecture: `IMPLEMENTATION_CONTEXT.md`
- Roadmap: `HANDOFF_NEXT_PHASE.md`
- Session summary: `HANDOFF_SESSION_2025_10_15.md`
- Feature specs: `docs/features/discovery/overview.md`
- Agent guide: `docs/agents/prompting-guide.md`

---

**You have everything you need. Start with Gap Analysis!** 🚀
