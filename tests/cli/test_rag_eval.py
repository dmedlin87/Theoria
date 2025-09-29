from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import pytest
from click.testing import CliRunner
from datasets import Dataset as HFDataset

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from theo.services.cli import rag_eval as rag_eval_module


class StubMetric:
    def __init__(self, name: str) -> None:
        self.name = name


class StubResult(dict):
    def __init__(self, scores: HFDataset, dataset: HFDataset) -> None:
        super().__init__()
        self.scores = scores
        self.dataset = dataset
        score_payload = scores.to_dict()
        for key, values in score_payload.items():
            numeric = [value for value in values if isinstance(value, (int, float))]
            if numeric:
                self[key] = sum(numeric) / len(numeric)


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


def test_rag_eval_reports_failures_and_regressions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runner: CliRunner) -> None:
    dev_path = tmp_path / "dev.jsonl"
    baseline_path = tmp_path / "baseline.json"
    output_path = tmp_path / "summary.json"

    _write_jsonl(
        dev_path,
        [
            {
                "id": "sample-1",
                "question": "What is grace?",
                "answer": "Grace is God's unmerited favour expressed in salvation.",
                "ground_truth": [
                    "Grace refers to God's unmerited favour, notably in salvation by faith."
                ],
                "contexts": [
                    "[1] For by grace you have been saved through faith.",
                    "[2] And this is not your own doing; it is the gift of God.",
                ],
                "citations": [
                    {
                        "index": 1,
                        "osis": "Eph 2:8",
                        "anchor": "context",
                        "snippet": "For by grace you have been saved through faith.",
                    }
                ],
            }
        ],
    )

    baseline_path.write_text(
        json.dumps(
            {
                "metrics": {
                    "faithfulness": 0.9,
                    "groundedness": 0.9,
                    "context_precision": 0.85,
                    "context_recall": 0.85,
                    "answer_relevance": 0.9,
                },
                "tolerance": 0.01,
            }
        ),
        encoding="utf-8",
    )

    scores = HFDataset.from_dict(
        {
            "faithfulness": [0.5],
            "groundedness": [0.6],
            "context_precision": [0.65],
            "context_recall": [0.62],
            "answer_relevance": [0.7],
        }
    )
    dataset = HFDataset.from_dict(
        {
            "question": ["What is grace?"],
            "answer": ["Grace is God's unmerited favour expressed in salvation."],
            "contexts": [[
                "[1] For by grace you have been saved through faith.",
                "[2] And this is not your own doing; it is the gift of God.",
            ]],
            "ground_truth": [[
                "Grace refers to God's unmerited favour, notably in salvation by faith."
            ]],
        }
    )

    stub_result = StubResult(scores=scores, dataset=dataset)

    monkeypatch.setattr(
        rag_eval_module,
        "_build_metrics",
        lambda: [StubMetric(name) for name in rag_eval_module.DEFAULT_THRESHOLDS],
    )
    monkeypatch.setattr(rag_eval_module, "ragas_evaluate", lambda dataset, metrics, in_ci: stub_result)

    result = runner.invoke(
        rag_eval_module.rag_eval,
        [
            "--dev-path",
            str(dev_path),
            "--trace-path",
            str(tmp_path / "missing.jsonl"),
            "--baseline",
            str(baseline_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code != 0
    assert "Low-scoring queries" in result.output
    assert "faithfulness: 0.500" in result.output
    assert output_path.exists()
    summary = json.loads(output_path.read_text("utf-8"))
    assert summary["failing_rows"] == ["sample-1"]
    assert summary["regressions"]
