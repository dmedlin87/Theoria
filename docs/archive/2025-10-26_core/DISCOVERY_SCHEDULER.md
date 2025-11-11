> **Archived on 2025-10-26**

# Discovery Scheduler - Background Auto-Discovery

## Overview

The Discovery Scheduler automatically generates discoveries for users in the background, eliminating the need for manual refresh. It runs as part of the FastAPI application lifecycle.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   FastAPI Application                    │
│  ┌───────────────────────────────────────────────────┐  │
│  │         Discovery Scheduler (APScheduler)         │  │
│  │                                                     │  │
│  │  ┌──────────────────────────────────────────────┐ │  │
│  │  │  Periodic Task (every 30 minutes)            │ │  │
│  │  │  - Find users with recent activity           │ │  │
│  │  │  - Refresh discoveries for each user         │ │  │
│  │  └──────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────┘  │
│                                                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │         Document Upload Endpoints                 │  │
│  │  - POST /api/ingest/file                          │  │
│  │  - POST /api/ingest/url                           │  │
│  │  - POST /api/ingest/transcript                    │  │
│  │                                                     │  │
│  │  Triggers: schedule_discovery_refresh()           │  │
│  │  (Background task runs immediately after upload)  │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Components

### 1. Discovery Scheduler (`theo/infrastructure/api/app/workers/discovery_scheduler.py`)

**Purpose:** Manages periodic background discovery generation

**Key Features:**
- Runs every 30 minutes by default
- Finds users with recent document activity (last 7 days)
- Refreshes discoveries for each active user
- Graceful startup/shutdown with FastAPI lifecycle

**Configuration:**
```python
# Default interval: 30 minutes
scheduler.add_job(
    func=self._refresh_all_users,
    trigger=IntervalTrigger(minutes=30),
    id="discovery_refresh",
)
```

### 2. Background Tasks (`theo/infrastructure/api/app/discoveries/tasks.py`)

**Purpose:** Execute discovery refresh in background after document uploads

**Key Functions:**
- `schedule_discovery_refresh()` - Queue discovery refresh as background task
- `run_discovery_refresh()` - Execute refresh in fresh database session

**Integration Points:**
- Called after every document upload
- Runs asynchronously without blocking response
- Uses FastAPI BackgroundTasks

### 3. Discovery Service (`theo/infrastructure/api/app/discoveries/service.py`)

**Purpose:** Core business logic for discovery generation

**Key Method:**
```python
def refresh_user_discoveries(self, user_id: str) -> list[Discovery]:
    """
    1. Load document embeddings for user
    2. Run pattern detection engine (DBSCAN clustering)
    3. Delete old pattern discoveries
    4. Persist new discoveries
    5. Create corpus snapshot
    """
```

## How It Works

### Automatic Discovery Flow

```
1. User uploads document
   ↓
2. Document is ingested and embedded
   ↓
3. schedule_discovery_refresh() is called (background task)
   ↓
4. run_discovery_refresh() executes in background
   ↓
5. DiscoveryService.refresh_user_discoveries()
   ↓
6. PatternDiscoveryEngine.detect() runs DBSCAN clustering
   ↓
7. New discoveries are persisted to database
   ↓
8. User sees new discoveries in /discoveries feed
```

### Periodic Refresh Flow

```
Every 30 minutes:
   ↓
1. Scheduler wakes up
   ↓
2. Query for users with recent activity (last 7 days)
   ↓
3. For each active user:
   - Load document embeddings
   - Run pattern detection
   - Update discoveries
   ↓
4. Log results and continue
```

## Configuration

### Environment Variables

```bash
# Discovery scheduler interval (minutes)
THEORIA_DISCOVERY_INTERVAL=30

# Minimum cluster size for pattern detection
THEORIA_DISCOVERY_MIN_CLUSTER=3

# DBSCAN epsilon (cosine distance threshold)
THEORIA_DISCOVERY_EPS=0.35

# Activity window for periodic refresh (days)
THEORIA_DISCOVERY_ACTIVITY_WINDOW=7
```

### Disabling Scheduler

To disable the periodic scheduler (e.g., in development):

```bash
# Set environment variable
THEORIA_DISABLE_DISCOVERY_SCHEDULER=true
```

Or modify `main.py`:
```python
# Comment out scheduler startup
# start_discovery_scheduler()
```

## Monitoring

### Logs

The scheduler logs key events:

```
INFO: Discovery scheduler started successfully
INFO: Refreshing discoveries for 5 active users
INFO: Generated 12 discoveries for user abc123
INFO: Discovery refresh completed for all users
INFO: Discovery scheduler stopped
```

### Metrics

Track discovery generation:
- Number of discoveries generated per user
- Time taken for refresh
- Pattern detection success rate
- Active users count

## Performance Considerations

### Resource Usage

**Memory:**
- Loads all document embeddings for each user into memory
- DBSCAN clustering is memory-intensive for large corpora
- Recommendation: 8GB+ RAM for 1000+ documents per user

**CPU:**
- DBSCAN is CPU-bound (O(n²) worst case)
- Runs in background thread, doesn't block API requests
- Recommendation: Multi-core CPU for multiple concurrent users

**Database:**
- Deletes and recreates pattern discoveries on each refresh
- Uses transactions to ensure consistency
- Recommendation: Connection pooling with 10+ connections

### Optimization Strategies

1. **Incremental Updates** (Future)
   - Only re-cluster new documents
   - Cache previous cluster assignments
   - Update discoveries incrementally

2. **Batch Processing** (Future)
   - Group users by corpus size
   - Process small corpora more frequently
   - Process large corpora less frequently

3. **Sampling** (Future)
   - For very large corpora (10k+ documents)
   - Sample representative subset for clustering
   - Full refresh on-demand only

## Testing

### Unit Tests

```bash
# Test discovery scheduler
pytest tests/api/workers/test_discovery_scheduler.py -v

# Test background tasks
pytest tests/api/discoveries/test_tasks.py -v
```

### Integration Tests

```bash
# Test end-to-end flow
pytest tests/api/test_discovery_integration.py -v
```

### Manual Testing

1. Start the API: `.\start-theoria.ps1`
2. Upload a document: POST `/api/ingest/file`
3. Wait ~5 seconds for background task
4. Check discoveries: GET `/api/discoveries`
5. Wait 30 minutes for periodic refresh
6. Check logs for scheduler activity

## Troubleshooting

### Scheduler Not Starting

**Symptom:** No "Discovery scheduler started" log message

**Causes:**
- APScheduler not installed: `pip install apscheduler`
- Import error in `discovery_scheduler.py`
- Exception during startup (check logs)

**Solution:**
```bash
# Check logs for errors
tail -f logs/api.log | grep -i discovery

# Verify APScheduler installed
pip show apscheduler
```

### Discoveries Not Generating

**Symptom:** No new discoveries after document upload

**Causes:**
- Background task not triggered
- Insufficient documents (need 3+ for clustering)
- Embeddings not generated
- Database connection error

**Solution:**
```bash
# Check background task logs
tail -f logs/api.log | grep -i "discovery refresh"

# Verify embeddings exist
psql $DATABASE_URL -c "SELECT COUNT(*) FROM passages WHERE embedding IS NOT NULL;"

# Manually trigger refresh
curl -X POST http://localhost:8000/api/discoveries/refresh \
  -H "Authorization: Bearer $TOKEN"
```

### High CPU Usage

**Symptom:** API server using 100% CPU

**Causes:**
- Large corpus (1000+ documents)
- DBSCAN clustering is expensive
- Too frequent refresh interval

**Solution:**
```bash
# Increase refresh interval
export THEORIA_DISCOVERY_INTERVAL=60  # 1 hour

# Reduce cluster size threshold
export THEORIA_DISCOVERY_MIN_CLUSTER=5

# Disable periodic refresh (keep upload-triggered only)
export THEORIA_DISABLE_DISCOVERY_SCHEDULER=true
```

## Future Enhancements

### 1. Celery Migration

For production deployments with multiple workers:

```python
# Replace APScheduler with Celery Beat
from celery import Celery
from celery.schedules import crontab

app = Celery('theoria')

@app.task
def refresh_all_discoveries():
    # Same logic as _refresh_all_users
    pass

app.conf.beat_schedule = {
    'refresh-discoveries': {
        'task': 'refresh_all_discoveries',
        'schedule': crontab(minute='*/30'),
    },
}
```

### 2. Priority Queue

Process high-value users first:

```python
# Priority based on:
# - Recent activity
# - Corpus size
# - User tier (free vs. paid)
users = sorted(active_users, key=lambda u: priority_score(u), reverse=True)
```

### 3. Smart Scheduling

Adjust frequency based on activity:

```python
# Active users: every 30 minutes
# Moderate users: every 2 hours
# Inactive users: daily
interval = calculate_interval(user_activity)
```

### 4. Discovery Types

Expand beyond pattern detection:

- **Contradictions** - NLI-based contradiction detection
- **Gaps** - BERTopic for missing topics
- **Connections** - Cross-reference analysis
- **Trends** - Time-series topic analysis
- **Anomalies** - Outlier detection

## Related Documentation

- [DISCOVERY_FEATURE.md](DISCOVERY_FEATURE.md) - Complete feature specification
- [AGENT_AND_PROMPTING_GUIDE.md](AGENT_AND_PROMPTING_GUIDE.md) - Agent architecture
- [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) - Reasoning framework

---

**Document Status:** v1.0  
**Last Updated:** 2025-01-15  
**Maintainer:** Theoria Development Team
