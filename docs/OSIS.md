# OSIS Normalization

Theo Engine uses the [OSIS](https://www.bibletechnologies.net/) schema to
normalize Bible references across the corpus.

## Detection Pipeline

1. Detect scripture mentions with regex tuned for ranges, multiple refs, and
   abbreviations.
2. Normalize via `pythonbible` to standard OSIS strings.
3. Store canonical references on each passage for Verse Aggregator queries.

## Range Handling

- Represent inclusive ranges (`John.1.1-John.1.5`).
- Support multi-book ranges.
- De-duplicate overlapping references before storage.
