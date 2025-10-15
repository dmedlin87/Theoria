# 🔍 Discovery Feature - Implementation Guide

## Overview

The Discovery Feed is Theoria's **intelligent auto-discovery engine** that automatically analyzes your research corpus and surfaces valuable insights, patterns, contradictions, and connections without requiring manual queries.

**Key Concept**: Transform Theoria from a search tool into a **proactive research companion** that works for you in the background.

## User Experience

### Two Modes of Research

| **Focused Research ("Hunter Mode")** | **Lazy Discovery ("Explorer Mode")** |
|--------------------------------------|---------------------------------------|
| I know what I'm looking for          | Show me what's interesting           |
| Query-driven (search bar)            | Browse-driven (discovery feed)       |
| Precision and specificity            | Serendipity and exploration          |
| Bottom-up (data → insight)           | Top-down (insights → data)           |

The Discovery feature enables **Explorer Mode** - perfect for lazy Sunday browsing, unexpected connections, and letting the system surprise you.

---

## Architecture

### Frontend (Next.js)

```
theo/services/web/app/discoveries/
├── page.tsx                         # Main discoveries page
├── discoveries.module.css           # Page styles
├── types.ts                         # TypeScript definitions
└── components/
    ├── DiscoveryCard.tsx            # Individual discovery card
    ├── DiscoveryCard.module.css     # Card styles
    ├── DiscoveryFilter.tsx          # Filter controls
    └── DiscoveryFilter.module.css   # Filter styles
```

### API Routes (Next.js)

```
theo/services/web/app/api/discoveries/
├── route.ts                         # GET /api/discoveries
└── [id]/
    ├── route.ts                     # DELETE /api/discoveries/:id
    ├── view/route.ts                # POST /api/discoveries/:id/view
    └── feedback/route.ts            # POST /api/discoveries/:id/feedback
```

### Backend (FastAPI) - To Be Implemented

```python
theo/services/api/app/routers/discoveries.py
theo/domain/discoveries/
├── engine.py           # Discovery analysis engine
├── detectors/
│   ├── pattern.py      # Pattern detection
│   ├── contradiction.py # Contradiction detection
│   ├── gap.py          # Gap analysis
│   ├── connection.py   # Connection finding
│   ├── trend.py        # Trend tracking
│   └── anomaly.py      # Anomaly detection
└── models.py           # SQLAlchemy models
```

---

## Discovery Types

### 1. **Pattern** 🔗
Thematic clusters across multiple documents.

**Example**: "8 documents discussing covenant theology with shared emphasis on the Abrahamic covenant"

**Use Cases**:
- Identify research themes you didn't consciously organize
- Find documents that should be studied together
- Discover emerging theological interests

### 2. **Contradiction** ⚠️
Conflicting interpretations or doctrinal positions.

**Example**: "Two sources present different views on justification - imputed vs. transformative righteousness"

**Use Cases**:
- Surface theological tensions in your corpus
- Compare Reformed vs. Catholic vs. Orthodox perspectives
- Prepare for debate or teaching on controversial topics

### 3. **Gap** 📊
Missing or underrepresented topics in your library.

**Example**: "50+ documents on soteriology but only 3 on pneumatology"

**Use Cases**:
- Identify blind spots in research coverage
- Ensure balanced theological study
- Guide future reading and uploads

### 4. **Connection** 🔄
Cross-references and thematic links between passages.

**Example**: "Isaiah 53 referenced across 12 NT passages on atonement"

**Use Cases**:
- Trace prophecy fulfillment chains
- Build sermon cross-reference lists
- Understand biblical theology development

### 5. **Trend** 📈
Changes in research activity over time.

**Example**: "340% increase in eschatology queries over 30 days"

**Use Cases**:
- Track sermon series preparation
- Understand your theological journey
- Anticipate future research needs

### 6. **Anomaly** 🎯
Unusual patterns that deviate from your norms.

**Example**: "Latest sermon cites Acts > Gospels (unusual for you)"

**Use Cases**:
- Spot unintentional citation bias
- Identify unique sermonic approaches
- Ensure biblical balance in preaching

---

## Data Model

### Discovery Object

```typescript
interface Discovery {
  id: string;
  type: DiscoveryType;
  title: string;
  description: string;
  confidence: number;        // 0-1 (ML model confidence)
  relevanceScore: number;    // 0-1 (personalized relevance)
  viewed: boolean;
  createdAt: string;
  userReaction?: "helpful" | "not_helpful" | "dismiss";
  metadata: DiscoveryMetadata;
}
```

### Type-Specific Metadata

Each discovery type has specialized metadata:

```typescript
{
  // Common fields
  relatedDocuments?: string[];
  relatedVerses?: string[];
  relatedTopics?: string[];
  
  // Pattern-specific
  patternData?: {
    clusterSize: number;
    sharedThemes: string[];
    keyVerses: string[];
  };
  
  // Contradiction-specific
  contradictionData?: {
    source1: string;
    source2: string;
    contradictionType: "doctrinal" | "interpretation" | "application";
    severity: "minor" | "moderate" | "major";
  };
  
  // And so on for each type...
}
```

---

## Backend Implementation Plan

### Phase 1: Foundation (MVP) ✅ COMPLETE
- [x] Frontend page and components
- [x] Mock API routes
- [x] Navigation integration
- [x] Command palette support

### Phase 2: Backend Integration (Next Steps)

#### 2.1 Database Schema

```sql
-- Discovery records
CREATE TABLE discoveries (
  id UUID PRIMARY KEY,
  user_id UUID,
  discovery_type VARCHAR(50),
  title TEXT NOT NULL,
  description TEXT,
  confidence FLOAT,
  relevance_score FLOAT,
  viewed BOOLEAN DEFAULT FALSE,
  user_reaction VARCHAR(20),
  created_at TIMESTAMP DEFAULT NOW(),
  metadata JSONB
);

-- Corpus evolution tracking
CREATE TABLE corpus_snapshots (
  id UUID PRIMARY KEY,
  user_id UUID,
  snapshot_date DATE,
  document_count INT,
  verse_coverage JSONB,
  dominant_themes JSONB,
  metadata JSONB
);

-- Indices
CREATE INDEX idx_discoveries_user_created ON discoveries(user_id, created_at DESC);
CREATE INDEX idx_discoveries_type ON discoveries(discovery_type);
CREATE INDEX idx_discoveries_viewed ON discoveries(user_id, viewed);
```

#### 2.2 FastAPI Endpoints

```python
# theo/services/api/app/routers/discoveries.py

@router.get("/discoveries")
async def list_discoveries(
    discovery_type: Optional[DiscoveryType] = None,
    viewed: Optional[bool] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(current_user)
):
    """List all discoveries for the current user."""
    pass

@router.post("/discoveries/{discovery_id}/view")
async def mark_viewed(
    discovery_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user)
):
    """Mark a discovery as viewed."""
    pass

@router.post("/discoveries/{discovery_id}/feedback")
async def submit_feedback(
    discovery_id: str,
    feedback: FeedbackRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user)
):
    """Submit user feedback (helpful/not helpful)."""
    pass

@router.delete("/discoveries/{discovery_id}")
async def dismiss_discovery(
    discovery_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user)
):
    """Dismiss/hide a discovery."""
    pass
```

#### 2.3 Background Analysis Job

```python
# theo/services/api/app/background/discovery_analyzer.py

async def analyze_corpus_for_discoveries(user_id: str):
    """
    Background task that runs after document upload or on schedule.
    Generates discoveries and stores them in the database.
    """
    
    # 1. Pattern Detection
    patterns = await detect_patterns(user_id)
    
    # 2. Contradiction Detection  
    contradictions = await detect_contradictions(user_id)
    
    # 3. Gap Analysis
    gaps = await analyze_gaps(user_id)
    
    # 4. Connection Finding
    connections = await find_connections(user_id)
    
    # 5. Trend Analysis
    trends = await analyze_trends(user_id)
    
    # 6. Anomaly Detection
    anomalies = await detect_anomalies(user_id)
    
    # Store all discoveries
    await store_discoveries([
        *patterns,
        *contradictions,
        *gaps,
        *connections,
        *trends,
        *anomalies
    ])
```

### Phase 3: ML Integration

#### 3.1 Pattern Detection (Clustering)

Use **pgvector embeddings** already in the system:

```python
from sklearn.cluster import DBSCAN
import numpy as np

async def detect_patterns(user_id: str) -> List[Discovery]:
    # 1. Get all document embeddings
    docs = await db.query(Document).filter_by(user_id=user_id).all()
    embeddings = np.array([doc.embedding for doc in docs])
    
    # 2. Cluster with DBSCAN
    clustering = DBSCAN(eps=0.3, min_samples=3, metric='cosine')
    labels = clustering.fit_predict(embeddings)
    
    # 3. For each cluster, extract shared themes
    discoveries = []
    for cluster_id in set(labels):
        if cluster_id == -1:  # Noise
            continue
            
        cluster_docs = [docs[i] for i, label in enumerate(labels) if label == cluster_id]
        
        # Extract common themes (TF-IDF or LDA)
        themes = extract_themes(cluster_docs)
        
        # Find key verses
        verses = extract_common_verses(cluster_docs)
        
        discovery = Discovery(
            type="pattern",
            title=f"{themes[0].title()} Cluster Detected",
            description=f"Found {len(cluster_docs)} documents with shared emphasis on {', '.join(themes[:3])}",
            confidence=calculate_cluster_confidence(cluster_docs),
            metadata={
                "patternData": {
                    "clusterSize": len(cluster_docs),
                    "sharedThemes": themes,
                    "keyVerses": verses
                },
                "relatedDocuments": [d.id for d in cluster_docs]
            }
        )
        discoveries.append(discovery)
    
    return discoveries
```

#### 3.2 Contradiction Detection

```python
from transformers import pipeline

# Use a sentence similarity model
similarity_model = pipeline("sentence-similarity", model="sentence-transformers/all-MiniLM-L6-v2")

async def detect_contradictions(user_id: str) -> List[Discovery]:
    # 1. Get all document passages on same topics
    topic_passages = await group_passages_by_topic(user_id)
    
    contradictions = []
    for topic, passages in topic_passages.items():
        # 2. Compare pairs for contradiction
        for i, p1 in enumerate(passages):
            for p2 in passages[i+1:]:
                # Use NLI model to detect entailment/contradiction
                result = classify_relationship(p1.text, p2.text)
                
                if result == "contradiction" and confidence > 0.7:
                    contradictions.append(Discovery(
                        type="contradiction",
                        title=f"Conflicting Views on {topic}",
                        description=f"Two sources present different positions...",
                        confidence=confidence,
                        metadata={
                            "contradictionData": {
                                "source1": p1.document.title,
                                "source2": p2.document.title,
                                "contradictionType": "doctrinal",
                                "severity": determine_severity(confidence)
                            }
                        }
                    ))
    
    return contradictions
```

#### 3.3 Gap Analysis (Simple Stats)

```python
async def analyze_gaps(user_id: str) -> List[Discovery]:
    # 1. Count documents by theological topic
    topic_counts = await db.query(
        Document.metadata['topics'].label('topic'),
        func.count().label('count')
    ).filter_by(user_id=user_id).group_by('topic').all()
    
    # 2. Identify underrepresented topics
    avg_count = sum(c for _, c in topic_counts) / len(topic_counts)
    
    gaps = []
    for topic, count in topic_counts:
        if count < avg_count * 0.2:  # Less than 20% of average
            gaps.append(Discovery(
                type="gap",
                title=f"Limited Coverage of {topic}",
                description=f"Only {count} documents on {topic} vs {int(avg_count)} average",
                confidence=0.95,  # High confidence - it's just counting
                metadata={
                    "gapData": {
                        "missingTopic": topic,
                        "relatedQueries": generate_query_suggestions(topic)
                    }
                }
            ))
    
    return gaps
```

---

## ML Strategy

### What to Use ML For

✅ **Yes - High ROI:**
1. **Embeddings for clustering** - Use existing pgvector embeddings
2. **Topic modeling** - LDA or BERTopic for theme extraction
3. **Classification** - Theological stance detection (Reformed, Catholic, etc.)
4. **Similarity** - Find similar documents/passages
5. **NLI** - Detect contradictions (entailment/contradiction/neutral)

⚠️ **Maybe - Medium ROI:**
6. **Trend forecasting** - Predict future research interests
7. **Personalization** - Learn user preferences for discovery relevance

❌ **No - Low ROI / Overkill:**
8. **Deep learning from scratch** - Use pre-trained models instead
9. **Custom LLMs** - Expensive, use OpenAI/Anthropic for generation
10. **Complex neural nets** - Start simple (scikit-learn), upgrade if needed

### Recommended Stack

```python
# Core ML Libraries
sklearn              # Clustering, classification
sentence-transformers # Embeddings (already using via pgvector)
transformers         # NLI, zero-shot classification
gensim               # Topic modeling (LDA)
bertopic             # Modern topic modeling

# Optional Advanced
spacy                # NER for extracting theological terms
flair                # Few-shot classification
```

---

## Triggering Discovery Analysis

### When to Run

1. **After document upload** - Analyze immediately
2. **On schedule** - Nightly batch job for all users
3. **On demand** - User clicks "Refresh" button
4. **Webhook** - When external sources update

### Implementation

```python
# In upload handler
@router.post("/documents/upload")
async def upload_document(...):
    # ... save document ...
    
    # Trigger background analysis
    background_tasks.add_task(
        analyze_corpus_for_discoveries,
        user_id=user.id,
        trigger="upload"
    )
    
    return {"document_id": doc.id}


# Scheduled job (Celery/APScheduler)
@scheduler.scheduled_job('cron', hour=2)  # 2 AM daily
async def nightly_discovery_analysis():
    users = await db.query(User).all()
    for user in users:
        await analyze_corpus_for_discoveries(user.id)
```

---

## Frontend Integration

### Update Next.js API Routes

Replace mock data in `app/api/discoveries/route.ts`:

```typescript
export async function GET() {
  const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
  const apiKey = process.env.THEO_SEARCH_API_KEY;
  
  const response = await fetch(`${backendUrl}/api/discoveries`, {
    headers: {
      "Authorization": `Bearer ${apiKey}`,
    },
  });
  
  if (!response.ok) {
    throw new Error("Failed to fetch discoveries");
  }
  
  return NextResponse.json(await response.json());
}
```

---

## Future Enhancements

### Phase 4: Advanced Features

1. **Discovery Feed Personalization**
   - Learn from user feedback (helpful/not helpful)
   - Adjust relevance scores based on interaction history
   - Suppress discovery types user ignores

2. **Notification System**
   - Email digest: "5 new discoveries this week"
   - Browser push notifications
   - Slack/Discord webhooks

3. **Discovery Insights Dashboard**
   - Network graph visualization of connections
   - Timeline of research evolution
   - Corpus analytics (word clouds, heat maps)

4. **"Surprise Me" Button**
   - Random high-value discovery
   - Serendipity engine for exploration

5. **Collaborative Discoveries**
   - Share discoveries with team members
   - Comment on discoveries
   - Upvote/downvote community discoveries

---

## Testing

### Frontend Testing

```bash
cd theo/services/web
npm run test:vitest -- discoveries
npm run test:e2e -- --grep "discoveries"
```

### Backend Testing

```bash
pytest tests/api/discoveries/
pytest tests/ml/discovery_engine/
```

### Integration Testing

1. Upload test documents
2. Trigger discovery analysis
3. Verify discoveries appear in UI
4. Test filtering, viewing, feedback
5. Check database persistence

---

## Monitoring & Metrics

Track these metrics:

- **Discovery generation rate** - How many per user per day?
- **Discovery view rate** - What % get clicked?
- **Feedback ratio** - Helpful vs not helpful
- **Type distribution** - Which discovery types are most common?
- **Confidence scores** - Is the ML model accurate?
- **User engagement** - Time spent on discoveries page

---

## Conclusion

The Discovery Feed transforms Theoria into a **proactive research assistant** that:

✨ Surfaces insights you wouldn't find manually  
🔄 Connects disparate parts of your corpus  
📊 Identifies gaps and growth areas  
⚡ Works in the background while you research  
🎯 Learns your preferences over time  

**Next Steps:**
1. ✅ Frontend complete - test in browser
2. ⏳ Implement FastAPI backend endpoints
3. ⏳ Build discovery analysis engine
4. ⏳ Integrate ML models for pattern detection
5. ⏳ Add background job scheduling
6. ⏳ Deploy and monitor

Let's make research discovery effortless! 🚀
