import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.slow
def test_train_and_eval_scripts(tmp_path):
    project_root = Path(__file__).resolve().parents[2]

    feedback_path = project_root / "tests" / "ranking" / "data" / "feedback_events.jsonl"
    holdout_path = project_root / "tests" / "ranking" / "data" / "holdout.json"

    model_path = tmp_path / "reranker.joblib"
    report_path = tmp_path / "metrics.json"

    train_cmd = [
        sys.executable,
        str(project_root / "scripts" / "train_reranker.py"),
        "--feedback-path",
        str(feedback_path),
        "--model-output",
        str(model_path),
        "--lookback-days",
        "10",
        "--reference-time",
        "2025-02-21T00:00:00Z",
    ]

    subprocess.run(train_cmd, check=True)
    assert model_path.exists()

    eval_cmd = [
        sys.executable,
        str(project_root / "scripts" / "eval_reranker.py"),
        "--checkpoint",
        str(model_path),
        "--holdout-path",
        str(holdout_path),
        "--k",
        "2",
        "--report-path",
        str(report_path),
    ]

    result = subprocess.run(eval_cmd, check=True, capture_output=True, text=True)
    output = result.stdout
    assert "Baseline metrics" in output
    assert "Reranked metrics" in output

    assert report_path.exists()
    metrics_payload = json.loads(report_path.read_text())
    assert set(metrics_payload.keys()) >= {"baseline", "reranked", "k", "queries"}
    assert metrics_payload["k"] == 2
    assert metrics_payload["queries"] > 0
