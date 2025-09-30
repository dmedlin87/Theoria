"""Train a lightweight learning-to-rank model from feedback events.

Usage
-----

```
python scripts/train_reranker.py \
    --feedback-path data/eval/reranker/train_feedback_events.jsonl \
    --model-output data/eval/reranker/reranker.joblib \
    --lookback-days 30
```

The feedback file may be JSONL (one document per line), JSON (list of
documents) or CSV. Each record should include at least the following
fields:

* ``created_at`` – ISO-8601 timestamp, used with ``--lookback-days``.
* ``query_id`` and ``document_id`` – identifiers for grouping.
* ``label`` – numeric relevance target, e.g. 1 for positive feedback.
* Either a nested ``features`` mapping or numeric top-level fields used as
  model features. ``baseline_rank`` and ``baseline_score`` are included
  automatically when present.

The resulting joblib checkpoint stores the fitted scikit-learn pipeline and
the feature column order used for inference.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import joblib
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import HistGradientBoostingRegressor


Record = Dict[str, object]


@dataclass
class Dataset:
    features: List[List[float]]
    labels: List[float]
    feature_columns: List[str]


NUMERIC_TOP_LEVEL_FIELDS = {"baseline_rank", "baseline_score"}
RESERVED_KEYS = {"created_at", "query_id", "document_id", "label", "features"}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a reranker from feedback events")
    parser.add_argument("--feedback-path", type=Path, required=True, help="Path to feedback events JSON/CSV")
    parser.add_argument("--model-output", type=Path, required=True, help="Destination joblib checkpoint path")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=30,
        help="Number of days of feedback to include (default: 30)",
    )
    parser.add_argument(
        "--reference-time",
        type=str,
        default=None,
        help="Optional ISO-8601 timestamp used instead of the current time when applying the lookback window",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=17,
        help="Random seed passed to HistGradientBoostingRegressor",
    )
    return parser.parse_args(argv)


def load_feedback_events(path: Path) -> List[Record]:
    if not path.exists():
        raise FileNotFoundError(f"Feedback events file not found: {path}")

    if path.suffix.lower() in {".json", ".jsonl"}:
        return _load_json_feedback(path)
    if path.suffix.lower() == ".csv":
        return _load_csv_feedback(path)
    raise ValueError(f"Unsupported feedback format: {path.suffix}")


def _load_json_feedback(path: Path) -> List[Record]:
    records: List[Record] = []
    with path.open("r", encoding="utf-8") as handle:
        if path.suffix.lower() == ".jsonl":
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
        else:
            payload = json.load(handle)
            if isinstance(payload, list):
                records.extend(payload)
            else:
                raise ValueError("JSON feedback payload must be a list of records")
    return records


def _load_csv_feedback(path: Path) -> List[Record]:
    records: List[Record] = []
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            record: Record = {}
            for key, value in row.items():
                if value is None or value == "":
                    continue
                record[key] = _maybe_cast_numeric(value)
            records.append(record)
    return records


def _maybe_cast_numeric(value: str) -> object:
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # Ensure timezone awareness by falling back to UTC.
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    raise TypeError(f"Unsupported datetime value: {value!r}")


def filter_recent_events(records: Iterable[Record], cutoff: datetime) -> List[Record]:
    filtered: List[Record] = []
    for record in records:
        created_at = record.get("created_at")
        if created_at is None:
            continue
        try:
            created_dt = _parse_datetime(created_at)
        except Exception:  # pragma: no cover - defensive programming
            continue
        if created_dt >= cutoff:
            filtered.append(record)
    return filtered


def extract_features(record: Record) -> Dict[str, float]:
    features: Dict[str, float] = {}

    nested = record.get("features")
    if isinstance(nested, dict):
        for key, value in nested.items():
            if isinstance(value, (int, float)):
                features[key] = float(value)

    for key, value in record.items():
        if key in RESERVED_KEYS:
            continue
        if isinstance(value, (int, float)):
            features.setdefault(key, float(value))

    for key in NUMERIC_TOP_LEVEL_FIELDS:
        value = record.get(key)
        if isinstance(value, (int, float)):
            features.setdefault(key, float(value))

    return features


def build_dataset(records: Iterable[Record]) -> Dataset:
    raw_rows: List[Dict[str, float]] = []
    labels: List[float] = []
    feature_names: set[str] = set()

    for record in records:
        if "label" not in record:
            continue
        try:
            label = float(record["label"])
        except (TypeError, ValueError):
            continue

        features = extract_features(record)
        if not features:
            continue

        feature_names.update(features.keys())
        raw_rows.append(features)
        labels.append(label)

    if not raw_rows:
        raise ValueError("No valid training examples found in feedback events")

    feature_columns = sorted(feature_names)
    rows = [
        [float(row.get(column, 0.0)) for column in feature_columns]
        for row in raw_rows
    ]

    return Dataset(features=rows, labels=labels, feature_columns=feature_columns)


def train_model(dataset: Dataset, random_state: int) -> Pipeline:
    pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value=0.0)),
            ("scaler", StandardScaler()),
            (
                "model",
                HistGradientBoostingRegressor(
                    random_state=random_state,
                    max_depth=6,
                    learning_rate=0.1,
                    max_bins=32,
                ),
            ),
        ]
    )
    pipeline.fit(dataset.features, dataset.labels)
    return pipeline


def save_checkpoint(model: Pipeline, feature_columns: List[str], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"model": model, "feature_columns": feature_columns}
    joblib.dump(payload, output_path)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    reference_time = datetime.now(tz=timezone.utc)
    if args.reference_time:
        reference_time = _parse_datetime(args.reference_time)

    all_records = load_feedback_events(args.feedback_path)
    cutoff = reference_time - timedelta(days=args.lookback_days)
    recent_records = filter_recent_events(all_records, cutoff)
    if not recent_records:
        raise ValueError("No feedback events within the requested lookback window")

    dataset = build_dataset(recent_records)
    model = train_model(dataset, random_state=args.random_state)
    save_checkpoint(model, dataset.feature_columns, args.model_output)

    print(f"Trained on {len(dataset.labels)} examples from {len(recent_records)} feedback events.")
    print(f"Feature columns: {', '.join(dataset.feature_columns)}")
    print(f"Checkpoint saved to {args.model_output}")

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

