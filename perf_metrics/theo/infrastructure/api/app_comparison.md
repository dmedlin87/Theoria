# RAG Evaluation Summary: theo/infrastructure/api/app

## Baseline (before)
- answer_relevance: 0.900
- context_precision: 0.880
- context_recall: 0.900
- faithfulness: 0.920
- groundedness: 0.900

## Current (after)
- answer_relevance: 0.010
- context_precision: 1.000
- context_recall: 1.000
- faithfulness: 1.000
- groundedness: 0.747

## Regressions detected
- groundedness: 0.747 vs baseline 0.900 (tolerance 0.020)
- answer_relevance: 0.010 vs baseline 0.900 (tolerance 0.020)