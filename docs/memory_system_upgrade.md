# Theoria Memory System Upgrade — Product & Engineering Spec

## Goal

Evolve Theoria's chat memory into a resilient, user-controlled system that behaves like a modern assistant by replacing flat caps with scored retention, adding hybrid retrieval with reciprocal rank fusion (RRF), deduplicating near-duplicates, exposing pin/forget/incognito workflows, enriching metadata, and asynchronously backfilling embeddings.

## Scope & Delivery Sequence

1. Storage and schema changes.
2. Write-path updates (deduplication and importance scoring).
3. Retrieval enhancements (hybrid search, RRF, and tri-score ranking).
4. Background worker for embedding backfill.
5. Memory management APIs and UI (pin/forget/incognito controls).
6. Telemetry and evaluations.
7. Stretch: aging and summarization.

## Key References

- Generative Agents (ACM Digital Library) for tri-score retrieval balancing relevance, recency, and importance.
- Weaviate and Microsoft Learn documentation for hybrid search patterns and RRF.
- OpenSearch documentation for reciprocal rank fusion.
- Google Research materials on SimHash for near-duplicate detection.
- OpenAI and Anthropic UX patterns for user-facing memory controls.

## Data Model Changes

Add or update the following fields on `memory_entries` (or the equivalent table):

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key. |
| `user_id` | UUID | Owning user. |
| `space` | String | Namespace or project identifier. |
| `role` | Enum | Speaker role (user, assistant, system). |
| `text` | Text | Original memory content. |
| `created_at` | Timestamp | Creation time. |
| `embedding` | Vector (nullable) | Dense embedding for semantic retrieval. |
| `needs_embedding` | Bool (default `true`) | Indicates that an embedding job must run. |
| `simhash` | Unsigned 64-bit | Used for near-duplicate detection. |
| `repeat_count` | Integer (default `0`) | Number of deduplicated repeats. |
| `tags` | String[] | Derived tags and entities. |
| `source_ids` | String[] | External provenance references. |
| `metadata_confidence` | Float 0–1 | Confidence score for metadata extraction. |
| `importance` | Float 0–1 | Long-term value score. |
| `pinned` | Bool | Explicitly pinned by the user. |
| `manually_saved` | Bool | Created via explicit user action. |
| `last_scores` | JSON (optional) | Cached breakdown of relevance, recency, importance, and total scores. |

Migration tasks:

- Backfill `simhash` values for all existing entries.
- Set `needs_embedding = true` where `embedding IS NULL`.
- Enforce a configurable soft cap (initially 200 entries per user/space).

## Write Path Policy

### Normalization

- Lowercase text, remove URLs and citations, and fold whitespace before processing.

### Near-Duplicate Detection

- Compute SimHash for the normalized text.
- If an existing entry in the same space has a Hamming distance ≤ 3, treat it as a near-duplicate:
  - Increment `repeat_count` on the canonical entry.
  - Recompute `importance = clamp(base_importance + f(repeat_count), 0, 1)`.
  - OR the incoming `manually_saved` flag onto the canonical row and run pinning logic before returning so user intent persists.
  - Merge any new metadata (e.g., `tags`, `source_ids`) or manual-save state from the incoming event into the canonical row.
  - Do not create a new row.

### Importance Heuristics

- `+0.5` if the user explicitly requests saving or pinning; set `manually_saved = true`.
- `+0.3` for persistent preferences, commitments, or goals.
- `+0.2` when metadata extraction yields entities/tags with `metadata_confidence ≥ 0.6`.
- `−0.1` for ephemeral or low-signal chit-chat.

### Embedding Queueing

- Store the entry with `needs_embedding = true` and enqueue a job for `memory_embed_backfill`.

### Capacity Trimming

- When the soft cap is exceeded, drop the lowest total-scoring entries that are neither pinned nor manually saved.
- Total score equals `relevance + recency + importance`; relevance defaults to `0` on write.

### Persist Flow Pseudocode

```python
def persist_memory(user_id, space, text, manually_saved=False):
    norm = normalize(text)
    metadata = extract_metadata(norm)
    h = simhash64(norm)
    dupe = find_near_dupe(user_id, space, h, hamming_thresh=3)
    if dupe:
        dupe.repeat_count += 1
        dupe.importance = clamp(dupe.importance + repeat_boost(dupe.repeat_count), 0, 1)
        dupe.manually_saved = dupe.manually_saved or manually_saved
        dupe.tags = merge_tags(dupe.tags, metadata.tags)
        dupe.source_ids = merge_source_ids(dupe.source_ids, metadata.source_ids)
        apply_pinning_policy(dupe, manually_saved=manually_saved)
        save(dupe)
        return dupe.id

    entry = Memory(
        user_id=user_id,
        space=space,
        text=text,
        simhash=h,
        needs_embedding=True,
        repeat_count=0,
        importance=score_importance(text, manually_saved),
        manually_saved=manually_saved,
        tags=metadata.tags,
        source_ids=metadata.source_ids,
    )
    apply_pinning_policy(entry, manually_saved=manually_saved)
    save(entry)
    enqueue_embed(entry.id)

    enforce_capacity(user_id, space)
    return entry.id
```

## Retrieval Policy

### Hybrid Retrieval with RRF

1. Run sparse retrieval (BM25/keyword) over `text` and `tags` scoped to the user/space.
2. Run dense retrieval (ANN) over embeddings; skip entries lacking embeddings.
3. Fuse sparse and dense rankings using reciprocal rank fusion with `k = 60` to avoid brittle score normalization.

### Tri-Score Re-Ranking

- **Relevance:** cosine similarity between the query embedding and entry embedding when available, otherwise normalized sparse score.
- **Recency:** exponential decay `recency = exp(-Δt / τ)` with `τ ≈ 7 days`.
- **Importance:** stored importance value.
- Compute `total = α * relevance + β * recency + γ * importance` with default weights `α = β = γ = 1`.
- Apply maximal marginal relevance (MMR) to ensure topical diversity.
- Select the top 8–16 entries within the token budget.

### Context Assembly

- Group by tags or entities to encourage topic spread.
- Include `source_ids` for provenance without inlining large payloads.
- Prefer concise memory summaries over raw text when entries are long.

### Retrieval Pseudocode

```python
def retrieve_memories(user_id, space, query_text, now, top_n=12):
    sparse = bm25_search(user_id, space, query_text)
    dense = vector_search(user_id, space, query_text)
    fused = rrf_fuse([sparse, dense], k=60)

    scored = []
    query_emb = embed_query(query_text)
    for mid in fused:
        m = load_memory(mid)
        rel = cosine(query_emb, m.embedding) if m.embedding else normalize_sparse_score(mid, sparse)
        rec = math.exp(-age_seconds(m.created_at, now) / tau_seconds)
        tot = alpha * rel + beta * rec + gamma * m.importance
        scored.append((tot, m))

    diverse = maximal_marginal_relevance(scored, key=lambda memory: memory.tags, k=top_n)
    return [memory for _, memory in diverse]
```

### Fallback Behavior

- If the vector store is unavailable, the sparse leg still returns results; RRF gracefully handles empty dense rankings.

## Metadata Enrichment

- When metadata is sparse, run named entity recognition and keyphrase extraction.
- Use embedding neighbors to propose tags when embeddings exist.
- Always carry `source_ids` for retrieval-augmented generation provenance.
- Compute `metadata_confidence` as the average detector confidence, clamped to `[0, 1]`.

## User Controls & Privacy

Expose REST endpoints under `/v1/memory`:

- `GET /summary?space=...` — human-readable summary of memories.
- `GET /entries?space=...` — list entries with filtering for `pinned` and `manually_saved`.
- `POST /entries` — create entries; accepts `{ text, space, tags?, manually_saved? }`.
- `POST /entries/:id/pin` and `DELETE /entries/:id/pin` — manage pinning.
- `DELETE /entries/:id` — forget an entry and store a 24-hour tombstone digest to prevent immediate recreation.
- `POST /settings` — set `{ memory_enabled: bool, incognito_default: bool }` per space.
- `POST /incognito/start` and `POST /incognito/end` — manage session-scoped incognito mode that skips persistence and retrieval.

In chat UX, support natural language commands such as "what do you remember about X?", "forget that", "pin this", "turn memory off", and "start incognito for this chat."

## Background Workers

- `memory_embed_backfill` batches embedding jobs with retry and jitter, marking `needs_embedding = false` upon success.
- Export metrics: backlog size, p95 time to embed, failure rate.
- Optional periodic aging: cluster older low-recency items, summarize into roll-up memories, and link back via `source_ids` while archiving or superseding the originals.

## Telemetry & Alerts

Track and alert on:

- Hybrid retrieval hit rate (percentage of turns where retrieved memory influenced the model).
- Dedupe saves from SimHash.
- Trim events per user/space, with alerts if a pinned item would be trimmed.
- Embedding backlog depth and age (alert when backlog exceeds thresholds).
- User actions: pins, unpins, deletes, memory enable/disable, and incognito usage.

## Evals & Testing

- Build ~20 synthetic tasks requiring memory (preferences, recurring meetings, multi-step goals).
- Compare model outputs with and without top-N memory to validate impact.
- Parameter sweeps for `α`, `β`, `γ`, `τ`, RRF `k`, and result count `N` to maximize accuracy and brevity.
- Simulate outages (e.g., disable vector store) to ensure sparse + RRF fallback maintains functionality.

## Security & Privacy Considerations

- Incognito sessions skip persistence and retrieval from durable storage.
- Prefer summarized forms for long-term storage to minimize sensitive data retention.
- Enforce per-space boundaries (e.g., "TheoEngine" vs. "PestIQ").
- Configure data retention (e.g., hard-delete non-pinned items older than 180 days after summarization).

## Acceptance Criteria (MVP)

- ✅ Hybrid retrieval with RRF provides useful results even when embeddings are unavailable.
- ✅ Tri-score relevance/recency/importance controls memory selection with tunable weights.
- ✅ SimHash deduplication prevents near-duplicate spam and boosts importance with repetition.
- ✅ Users can view, pin, forget, disable memory, and start incognito sessions; actions are auditable.
- ✅ Embedding backfill queue keeps `needs_embedding = false` under normal load; outages do not tank retrieval.
- ✅ Telemetry dashboards cover embedding backlog, trim events, hit rate, and user actions.

## Stretch Goals

- Conflict detection (e.g., updated meeting times) with confirmation prompts and superseding records.
- Cross-space opt-in sharing with explicit tags.
- Periodic topic roll-ups to reduce storage while preserving provenance.
