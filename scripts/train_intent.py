"""Utility script to train the Theo Engine chat intent classifier."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Sequence

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

DEFAULT_DATA_PATH = Path("data/intent_samples.csv")
DEFAULT_OUTPUT_PATH = Path("data/intent_classifier.joblib")
LABEL_SEPARATOR = "|||"


def _load_dataset(path: Path) -> tuple[list[str], list[str], list[str]]:
    texts: list[str] = []
    intents: list[str] = []
    stances: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            text = (row.get("text") or "").strip()
            intent = (row.get("intent") or "").strip()
            stance = (row.get("stance") or "").strip()
            if not text or not intent:
                continue
            texts.append(text)
            intents.append(intent)
            stances.append(stance)
    if not texts:
        raise ValueError("Dataset is empty or missing required columns")
    return texts, intents, stances


def _build_labels(intents: Sequence[str], stances: Sequence[str]) -> list[str]:
    labels: list[str] = []
    for intent, stance in zip(intents, stances, strict=False):
        if stance:
            labels.append(f"{intent}{LABEL_SEPARATOR}{stance}")
        else:
            labels.append(intent)
    return labels


def _train_pipeline(texts: Sequence[str], labels: Sequence[str]) -> Pipeline:
    pipeline = Pipeline(
        steps=[
            (
                "vectorizer",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    min_df=1,
                    max_df=0.9,
                    lowercase=True,
                    stop_words="english",
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1000,
                    solver="lbfgs",
                    multi_class="auto",
                    random_state=42,
                ),
            ),
        ]
    )
    pipeline.fit(texts, labels)
    return pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA_PATH,
        help="Path to a CSV file containing text,intent,stance columns",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Where to persist the trained model artifact",
    )
    args = parser.parse_args()

    texts, intents, stances = _load_dataset(args.data)
    labels = _build_labels(intents, stances)
    pipeline = _train_pipeline(texts, labels)

    unique_intents = sorted({intent for intent in intents if intent})
    unique_stances = sorted({stance for stance in stances if stance})
    intent_to_stances_map: defaultdict[str, set[str]] = defaultdict(set)
    for intent, stance in zip(intents, stances, strict=False):
        if intent and stance:
            intent_to_stances_map[intent].add(stance)

    label_schema = {
        "intents": unique_intents,
        "stances": unique_stances,
        "intent_to_stances": {
            intent: sorted(values)
            for intent, values in intent_to_stances_map.items()
        },
    }

    artifact = {
        "pipeline": pipeline,
        "label_schema": label_schema,
        "label_separator": LABEL_SEPARATOR,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, args.output)

    summary = {
        "examples": len(texts),
        "intents": label_schema["intents"],
        "stances": label_schema["stances"],
        "model_path": str(args.output),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
