# 🔍 Discovery Feature - Quick Start Guide

## What Is It?

The **Discovery Feed** is your AI research assistant that works in the background, automatically finding:

- 🔗 **Patterns** - Documents that cluster around shared themes
- ⚠️ **Contradictions** - Conflicting theological views in your corpus
- 📊 **Gaps** - Topics you're underrepresenting  
- 🔄 **Connections** - Cross-references between verses and documents
- 📈 **Trends** - Changes in your research focus over time
- 🎯 **Anomalies** - Unusual patterns that deviate from your norms

## Access It Now

### Option 1: Sidebar
1. Start Theoria: `.\start-theoria.ps1`
2. Open http://localhost:3000
3. Click **"Discoveries"** in the sidebar (Library section)

### Option 2: Command Palette
1. Press `Ctrl+K` (or `Cmd+K`)
2. Type "discoveries"
3. Press Enter

### Option 3: Direct URL
- http://localhost:3000/discoveries

## What You'll See

The page shows **6 example discoveries** to demonstrate the concept:

1. **Covenant Theology Cluster** - 8 documents with shared themes
2. **Justification Contradiction** - Reformed vs Orthodox views
3. **Pneumatology Gap** - You have 50 soteriology docs but only 3 on the Holy Spirit
4. **Isaiah 53 Connection** - Found across 12 NT passages
5. **Eschatology Trend** - 340% increase in queries
6. **Citation Anomaly** - Your latest sermon cited Acts more than Gospels

## Try These Features

### 🎯 Filter by Type
Click the filter buttons to see only:
- All Types
- Patterns
- Contradictions  
- Connections
- Gaps
- Trends
- Anomalies

### 🆕 Show New Only
Toggle "New only" to see just unviewed discoveries.

### 🔍 Explore Details
Click **"Show Details ▼"** to see:
- Cluster size and shared themes (patterns)
- Severity and type (contradictions)
- Missing topics (gaps)
- Related verses and documents

### ➡️ Explore Discovery
Click **"Explore →"** to navigate to:
- Verse pages (if related verses)
- Search results (if related topics)
- Research panels (for contradictions)

### 👍 Provide Feedback
After exploring, click 👍 or 👎 to help the system learn.

### ✕ Dismiss
Click the **✕** button to remove discoveries you don't want to see.

### ↻ Refresh
Click **"↻ Refresh"** to reload the discoveries.

## Current Status

✅ **Fully functional frontend** with mock data  
⏳ **Backend integration** coming next

Right now, you're seeing static example discoveries. Once the backend is connected, these will be **real insights from your actual corpus**.

## What's Next?

### For You (User)
- Explore the UI and provide feedback
- Think about what kinds of discoveries would be most valuable
- Consider what corpus gaps you want to fill

### For Development
- Implement FastAPI backend endpoints
- Build discovery analysis engine
- Add ML models for pattern detection
- Create background job scheduler
- Connect to real corpus data

## Key Insight

**Two modes of research:**

| Hunter Mode 🎯 | Explorer Mode 🔍 |
|----------------|------------------|
| I know what I want | Show me something interesting |
| Search-driven | Discovery-driven |
| Focused | Serendipitous |

The Discovery Feed is **Explorer Mode** - perfect for lazy Sunday browsing and unexpected insights.

## Documentation

- **Quick Start**: You're reading it! 📄
- **Full Docs**: [Discovery Feature Overview](overview.md) 📚
- **Implementation**: [DISCOVERY_IMPLEMENTATION_SUMMARY.md](../DISCOVERY_IMPLEMENTATION_SUMMARY.md) 🔧

## ML Strategy (Answer to Your Question)

> "Should we include ML or deep learning?"

**Yes! Strategic ML will be crucial:**

### ✅ Use ML For:
1. **Clustering** (pattern detection) - Use pgvector embeddings + DBSCAN/KMeans
2. **Classification** (theological stance detection) - Fine-tune BERT on theology corpus
3. **NLI** (contradiction detection) - Use pre-trained entailment models
4. **Topic modeling** - BERTopic or LDA for theme extraction
5. **Anomaly detection** - Statistical outlier detection + ML confidence

### ⚠️ Avoid:
1. **Deep learning from scratch** - Use pre-trained models (transformers)
2. **Custom LLMs** - Leverage OpenAI/Anthropic APIs for generation
3. **Over-engineering** - Start simple (scikit-learn), scale up if needed

### 🎯 The Strategy:
- **Embeddings**: Already have pgvector - use it!
- **Clustering**: Scikit-learn DBSCAN on embeddings
- **Classification**: HuggingFace transformers (zero-shot or fine-tuned)
- **NLI**: Use existing models like `facebook/bart-large-mnli`
- **Topic modeling**: BERTopic for theme extraction

**TL;DR**: Use ML strategically for specific tasks, not as a hammer looking for nails.

---

**Questions?** Check the full docs or ask for help! 🚀
