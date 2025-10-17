"""Evaluate a trained reranker against a holdout dataset.

Usage
-----

```
python scripts/eval_reranker.py \
    --checkpoint data/eval/reranker/reranker.joblib \
    --holdout-path data/eval/reranker/holdout.json \
    --k 10
```

The holdout file may be JSON, JSONL, or CSV. Each entry should contain a
``query_id`` and ``candidates`` describing the baseline ranking. Candidates
may specify features via a nested ``features`` mapping or numeric top-level
fields, mirroring ``train_reranker.py``.
"""

from __future__ import annotations

import argparse
import csv
import json
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import joblib

from ranking.metrics import batch_mrr, batch_ndcg_at_k, batch_recall_at_k
from scripts.mlflow_tracking import mlflow_run


Candidate = Dict[str, object]
QueryRecord = Dict[str, object]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a reranker against a holdout dataset")
    parser.add_argument("--checkpoint", type=Path, required=True, help="Path to a joblib checkpoint produced by train_reranker.py")
    parser.add_argument("--holdout-path", type=Path, required=True, help="Path to holdout data (JSON/CSV)")
    parser.add_argument("--k", type=int, default=10, help="Cut-off for nDCG/Recall calculations (default: 10)")
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help="Optional JSON file to store the computed metrics for CI reporting",
    )
    return parser.parse_args(argv)


def load_holdout(path: Path) -> List[QueryRecord]:
    if not path.exists():
        raise FileNotFoundError(f"Holdout dataset not found: {path}")

    suffix = path.suffix.lower()
    if suffix in {".json", ".jsonl"}:
        return _load_json_holdout(path)
    if suffix == ".csv":
        return _load_csv_holdout(path)
    raise ValueError(f"Unsupported holdout format: {suffix}")


def _load_json_holdout(path: Path) -> List[QueryRecord]:
    with path.open("r", encoding="utf-8") as handle:
        if path.suffix.lower() == ".jsonl":
            records = [json.loads(line) for line in handle if line.strip()]
        else:
            records = json.load(handle)
    if not isinstance(records, list):
        raise ValueError("JSON holdout payload must be a list")
    return records


def _load_csv_holdout(path: Path) -> List[QueryRecord]:
    grouped: Dict[str, QueryRecord] = {}
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            query_id = row.get("query_id")
            if not query_id:
                continue
            candidate: Candidate = {}
            for key, value in row.items():
                if value in (None, ""):
                    continue
                if key == "query_id":
                    continue
                candidate[key] = _maybe_cast_numeric(value)
            grouped.setdefault(query_id, {"query_id": query_id, "candidates": []})
            grouped[query_id]["candidates"].append(candidate)
    return list(grouped.values())


def _maybe_cast_numeric(value: str) -> object:
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def extract_features(record: Candidate, feature_columns: Sequence[str]) -> List[float]:
    features: Dict[str, float] = {}
    nested = record.get("features")
    if isinstance(nested, dict):
        for key, value in nested.items():
            if isinstance(value, (int, float)):
                features[key] = float(value)

    for key, value in record.items():
        if key in {"label", "features", "document_id", "baseline_rank", "baseline_score"}:
            continue
        if isinstance(value, (int, float)):
            features.setdefault(key, float(value))

    for key in ("baseline_rank", "baseline_score"):
        value = record.get(key)
        if isinstance(value, (int, float)):
            features.setdefault(key, float(value))

    return [float(features.get(column, 0.0)) for column in feature_columns]


def sort_baseline(candidates: List[Candidate]) -> List[Candidate]:
    def sort_key(item_with_index: tuple[int, Candidate]) -> tuple[float, float]:
        index, candidate = item_with_index
        if "baseline_rank" in candidate and isinstance(candidate["baseline_rank"], (int, float)):
            return float(candidate["baseline_rank"]), float(index)
        if "baseline_score" in candidate and isinstance(candidate["baseline_score"], (int, float)):
            return (-float(candidate["baseline_score"]), float(index))
        return (float(index), 0.0)

    return [candidate for _, candidate in sorted(enumerate(candidates), key=sort_key)]


def predict_scores(model, feature_columns: Sequence[str], candidates: List[Candidate]) -> List[float]:
    feature_matrix = [extract_features(candidate, feature_columns) for candidate in candidates]
    return list(model.predict(feature_matrix))


def evaluate_rankings(rankings: Iterable[List[float]], k: int) -> Dict[str, float]:
    rankings_list = list(rankings)
    return {
        "nDCG@%d" % k: batch_ndcg_at_k(rankings_list, k),
        "MRR": batch_mrr(rankings_list),
        "Recall@%d" % k: batch_recall_at_k(rankings_list, k),
    }


def parse_labels(candidates: Iterable[Candidate]) -> List[float]:
    labels: List[float] = []
    for candidate in candidates:
        try:
            labels.append(float(candidate.get("label", 0.0)))
        except (TypeError, ValueError):
            labels.append(0.0)
    return labels


def print_metrics(title: str, metrics: Dict[str, float]) -> None:
    print(f"{title} metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value:.4f}")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    checkpoint = joblib.load(args.checkpoint)
    model = checkpoint["model"]
    feature_columns = checkpoint["feature_columns"]

    queries = load_holdout(args.holdout_path)
    baseline_rankings: List[List[float]] = []
    reranked_rankings: List[List[float]] = []

    for query in queries:
        candidates = list(query.get("candidates", []))
        if not candidates:
            continue

        baseline_order = sort_baseline(candidates)
        baseline_labels = parse_labels(baseline_order)
        baseline_rankings.append(baseline_labels)

        scores = predict_scores(model, feature_columns, candidates)
        scored_candidates = list(zip(scores, candidates, range(len(candidates)), strict=False))
        reranked_order = [candidate for _, candidate, index in sorted(scored_candidates, key=lambda item: (-item[0], item[2]))]
        reranked_labels = parse_labels(reranked_order)
        reranked_rankings.append(reranked_labels)

    baseline_metrics = evaluate_rankings(baseline_rankings, args.k)
    reranked_metrics = evaluate_rankings(reranked_rankings, args.k)

    print_metrics("Baseline", baseline_metrics)
    print_metrics("Reranked", reranked_metrics)

    report_payload = {
        "baseline": baseline_metrics,
        "reranked": reranked_metrics,
        "k": args.k,
        "queries": len(reranked_rankings),
    }

    if args.report_path:
        args.report_path.parent.mkdir(parents=True, exist_ok=True)
        args.report_path.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")

    with mlflow_run("eval_reranker", tags={"script": "eval_reranker"}) as tracking:
        if tracking is not None:
            tracking.log_params(
                {
                    "checkpoint": str(args.checkpoint),
                    "holdout_path": str(args.holdout_path),
                    "k": args.k,
                    "queries": len(reranked_rankings),
                }
            )
            metric_payload = {}
            for key, value in baseline_metrics.items():
                metric_payload[f"baseline_{key}"] = value
            for key, value in reranked_metrics.items():
                metric_payload[f"reranked_{key}"] = value
            tracking.log_metrics(metric_payload)
            if args.report_path:
                tracking.log_artifact(str(args.report_path))
            else:
                with tempfile.TemporaryDirectory() as tmpdir:
                    metrics_path = Path(tmpdir) / "evaluation_metrics.json"
                    metrics_path.write_text(
                        json.dumps(report_payload, indent=2), encoding="utf-8"
                    )
                    tracking.log_artifact(str(metrics_path), artifact_path="evaluation")

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

