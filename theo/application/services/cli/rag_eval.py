"""Evaluate RAG responses against curated corpora using Ragas."""

from __future__ import annotations

import json
import math
import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
import inspect

import click
try:  # pragma: no cover - datasets is optional for unit tests
    from datasets import Dataset as HFDataset
except ImportError:  # pragma: no cover - allows stubbing in tests
    HFDataset = None  # type: ignore[assignment]
from packaging.version import InvalidVersion, Version
from sqlalchemy.orm import Session

from ..api.app.ai import rag as rag_service
from ..api.app.models.search import HybridSearchFilters, HybridSearchRequest
from ..api.app.retriever.hybrid import hybrid_search
from theo.application.services.bootstrap import resolve_application


APPLICATION_CONTAINER, _ADAPTER_REGISTRY = resolve_application()


def get_engine():  # pragma: no cover - transitional wiring helper
    return _ADAPTER_REGISTRY.resolve("engine")

try:  # pragma: no cover - optional dependency guard for tests
    import ragas
    from ragas import evaluate as ragas_evaluate
    from ragas.metrics import (
        answer_correctness,
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )
except ImportError:  # pragma: no cover - test environments may stub ragas
    ragas = None  # type: ignore[assignment]
    ragas_evaluate = None
    answer_correctness = None  # type: ignore[assignment]
    answer_relevancy = None  # type: ignore[assignment]
    context_precision = None  # type: ignore[assignment]
    context_recall = None  # type: ignore[assignment]
    faithfulness = None  # type: ignore[assignment]

RAGAS_VERSION: str | None = None
if 'ragas' in globals() and ragas is not None:  # type: ignore[name-defined]
    RAGAS_VERSION = getattr(ragas, "__version__", None)


DEFAULT_DEV_PATH = Path("data/eval/rag_dev.jsonl")
DEFAULT_TRACE_PATH = Path("data/eval/production_traces.jsonl")
DEFAULT_BASELINE_PATH = Path("data/eval/baseline.json")
DEFAULT_OUTPUT_PATH = Path("data/eval/latest_results.json")

DEFAULT_THRESHOLDS: Mapping[str, float] = {
    "faithfulness": 0.8,
    "groundedness": 0.8,
    "context_precision": 0.7,
    "context_recall": 0.7,
    "answer_relevance": 0.8,
}

DEFAULT_TOLERANCE = 0.02

_FAKE_LLM_RESPONSES = (
    "This is a mocked response generated for CI evaluation.",
) * 256


def _should_flatten_ground_truth() -> bool:
    """Return True when ragas expects string ground-truth columns."""

    if RAGAS_VERSION is None:
        return False
    try:
        return Version(RAGAS_VERSION) >= Version("0.1.22")
    except InvalidVersion:
        return False


@dataclass
class EvaluationRecord:
    """Normalised representation of a single evaluation row."""

    id: str
    question: str
    answer: str
    ground_truth: list[str]
    contexts: list[str]
    citations: list[dict[str, Any]]
    filters: HybridSearchFilters | None = None


def _ensure_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        return [str(item) for item in value]
    return [str(value)]


def _load_jsonl(path: Path) -> list[EvaluationRecord]:
    if not path.exists():
        return []
    records: list[EvaluationRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            record_id = str(payload.get("id") or payload.get("question"))
            contexts = payload.get("contexts") or []
            if contexts and isinstance(contexts[0], list):
                contexts = contexts[0]
            contexts_list = [str(item) for item in contexts]
            ground_truth = _ensure_list(payload.get("ground_truth"))
            citations_raw = payload.get("citations") or []
            if citations_raw and isinstance(citations_raw[0], list):
                citations_raw = citations_raw[0]
            filters_payload = payload.get("filters") or {}
            filters = HybridSearchFilters.model_validate(filters_payload)
            records.append(
                EvaluationRecord(
                    id=record_id,
                    question=str(payload.get("question", "")),
                    answer=str(payload.get("answer", "")),
                    ground_truth=[str(item) for item in ground_truth],
                    contexts=contexts_list,
                    citations=[
                        {str(key): value for key, value in dict(entry).items()}
                        for entry in citations_raw
                    ],
                    filters=filters,
                )
            )
    return records


def _refresh_contexts(record: EvaluationRecord, session: Session) -> None:
    request = HybridSearchRequest(
        query=record.question,
        filters=record.filters or HybridSearchFilters(),
        k=5,
    )
    results = hybrid_search(session, request)
    citations = rag_service.build_citations(results)
    record.contexts = [citation.snippet for citation in citations]
    record.citations = [citation.model_dump(mode="json") for citation in citations]


def _build_dataset(
    records: Sequence[EvaluationRecord], *, flatten_ground_truth: bool = False
) -> HFDataset:
    if HFDataset is None:
        raise click.ClickException("datasets is not installed; cannot build evaluation dataset.")
    if flatten_ground_truth:
        ground_truth_column = [
            "\n".join(item.ground_truth) if item.ground_truth else ""
            for item in records
        ]
    else:
        ground_truth_column = [item.ground_truth for item in records]
    data = {
        "question": [item.question for item in records],
        "answer": [item.answer for item in records],
        "contexts": [item.contexts for item in records],
        "ground_truth": ground_truth_column,
    }
    return HFDataset.from_dict(data)


def _compute_overall_scores(result: Any, metric_names: Sequence[str]) -> dict[str, float]:
    overall: dict[str, float] = {}
    for name in metric_names:
        value = result.get(name) if isinstance(result, dict) else getattr(result, name, None)
        if value is None and hasattr(result, "get"):
            value = result.get(name)
        if value is None:
            continue
        try:
            overall[name] = float(value)
        except (TypeError, ValueError):
            continue
    return overall


def _extract_per_sample_scores(result: Any, records: Sequence[EvaluationRecord]) -> list[dict[str, Any]]:
    scores_dataset = getattr(result, "scores", None)
    dataset = getattr(result, "dataset", None)
    if scores_dataset is None:
        return []
    score_columns = list(scores_dataset.column_names)
    scores_dict = scores_dataset.to_dict()
    dataset_rows: list[dict[str, Any]] = []
    if dataset is not None:
        dataset_data = dataset.to_dict()
        for idx in range(len(records)):
            dataset_rows.append({key: dataset_data[key][idx] for key in dataset_data})
    entries: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        row_scores: dict[str, float] = {}
        for column in score_columns:
            values = scores_dict.get(column) or []
            if index >= len(values):
                continue
            value = values[index]
            if value is None or (isinstance(value, float) and math.isnan(value)):
                continue
            row_scores[column] = float(value)
        payload = {
            "id": record.id,
            "question": record.question,
            "answer": record.answer,
            "contexts": record.contexts,
            "ground_truth": record.ground_truth,
            "citations": record.citations,
            "scores": row_scores,
        }
        if index < len(dataset_rows):
            payload["dataset_row"] = dataset_rows[index]
        entries.append(payload)
    return entries


def _load_baseline(path: Path) -> tuple[dict[str, float], float]:
    if not path.exists():
        return {}, DEFAULT_TOLERANCE
    try:
        data = json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError:
        return {}, DEFAULT_TOLERANCE
    metrics = data.get("metrics") if isinstance(data, Mapping) else None
    tolerance = data.get("tolerance") if isinstance(data, Mapping) else None
    parsed_metrics = {
        str(name): float(value)
        for name, value in (metrics or {}).items()
        if isinstance(value, (int, float))
    }
    parsed_tolerance = (
        float(tolerance)
        if isinstance(tolerance, (int, float))
        else DEFAULT_TOLERANCE
    )
    return parsed_metrics, parsed_tolerance


def _save_baseline(path: Path, metrics: Mapping[str, float], tolerance: float) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "tolerance": tolerance,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_summary(path: Path, summary: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _build_metrics() -> list[Any]:
    metric_factories = {
        "faithfulness": faithfulness,
        "groundedness": answer_correctness,
        "context_precision": context_precision,
        "context_recall": context_recall,
        "answer_relevance": answer_relevancy,
    }

    missing = [name for name, factory in metric_factories.items() if factory is None]
    if missing:
        raise click.ClickException(
            "ragas and its metric dependencies are not available."
        )

    metrics: list[Any] = []
    for label, factory in metric_factories.items():
        metric = factory() if callable(factory) else factory
        try:
            metric.name = label
        except AttributeError:
            pass
        metrics.append(metric)
    return metrics


def _resolve_llm() -> Any | None:
    """Return a LangChain-backed fake LLM when API keys are unavailable."""

    if os.getenv("OPENAI_API_KEY") or os.getenv("RAGAS_OPENAI_API_KEY"):
        return None

    try:
        from ragas.llms import LangchainLLMWrapper
        from langchain_community.chat_models.fake import FakeListChatModel
        from langchain_core.language_models.chat_models import SimpleChatModel
        from langchain_core.messages import BaseMessage
    except ImportError:  # pragma: no cover - optional dependency missing
        return None

    class _DeterministicRagasChatModel(SimpleChatModel):
        """Return structured JSON that satisfies ragas parsers."""

        def _call(  # type: ignore[override]
            self,
            messages: list[BaseMessage],
            stop: list[str] | None = None,
            run_manager: Any | None = None,  # noqa: ARG002 - interface requirement
            **kwargs: Any,  # noqa: ANN401 - external API
        ) -> str:
            prompt = messages[-1].content if messages else ""
            lower_prompt = prompt.lower()

            if "verify if the context was useful" in lower_prompt:
                payload = {
                    "reason": "Context judged useful by CI stub.",
                    "verdict": 1,
                }
                return json.dumps(payload)

            if (
                "generate a question for the given answer" in lower_prompt
                or "noncommittal" in lower_prompt
            ):
                payload = {
                    "question": "What question best matches this answer?",
                    "noncommittal": 0,
                }
                return json.dumps(payload)

            if "classify them in one of the following categories" in lower_prompt:
                payload = {
                    "TP": [
                        {
                            "statement": "Stubbed statement aligns with ground truth.",
                            "reason": "Generated by CI stub to satisfy schema.",
                        }
                    ],
                    "FP": [],
                    "FN": [],
                }
                return json.dumps(payload)

            if (
                "analyze each sentence in the answer" in lower_prompt
                and "binary classification" in lower_prompt
            ):
                payload = [
                    {
                        "statement": "Stubbed sentence attributed to context.",
                        "reason": "Generated by CI stub to satisfy schema.",
                        "attributed": 1,
                    }
                ]
                return json.dumps(payload)

            if "judge the faithfulness of a series of statements" in lower_prompt:
                payload = [
                    {
                        "statement": "Stubbed faithful statement.",
                        "reason": "Generated by CI stub to satisfy schema.",
                        "verdict": 1,
                    }
                ]
                return json.dumps(payload)

            if (
                "break down each sentence into one or more fully understandable statements"
                in lower_prompt
            ):
                payload = [
                    {
                        "sentence_index": 0,
                        "simpler_statements": [
                            "Stubbed simplified statement generated for CI."
                        ],
                    }
                ]
                return json.dumps(payload)

            # Fallback: emulate FakeListChatModel behaviour for unknown prompts.
            return FakeListChatModel(responses=list(_FAKE_LLM_RESPONSES))._call(messages)

        @property
        def _llm_type(self) -> str:
            return "deterministic-ragas-chat-model"

        @property
        def _identifying_params(self) -> dict[str, Any]:
            return {}

    return LangchainLLMWrapper(_DeterministicRagasChatModel())


def _resolve_embeddings() -> Any | None:
    """Return fake embeddings when OpenAI access is unavailable."""

    if os.getenv("OPENAI_API_KEY") or os.getenv("RAGAS_OPENAI_API_KEY"):
        return None

    try:
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from langchain_community.embeddings import FakeEmbeddings
    except ImportError:  # pragma: no cover - optional dependency missing
        return None

    fake_embeddings = FakeEmbeddings(size=768)
    return LangchainEmbeddingsWrapper(fake_embeddings)


def _format_score(value: float | None) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return f"{value:.3f}"


@click.command("rag-eval")
@click.option("--dev-path", type=click.Path(path_type=Path), default=DEFAULT_DEV_PATH)
@click.option(
    "--trace-path",
    type=click.Path(path_type=Path),
    default=DEFAULT_TRACE_PATH,
)
@click.option(
    "--baseline",
    "baseline_path",
    type=click.Path(path_type=Path),
    default=DEFAULT_BASELINE_PATH,
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=DEFAULT_OUTPUT_PATH,
)
@click.option(
    "--update-baseline",
    is_flag=True,
    default=False,
    help="Persist the new aggregate scores as the baseline.",
)
@click.option(
    "--tolerance",
    type=float,
    default=None,
    help="Override the allowed regression tolerance.",
)
def rag_eval(
    dev_path: Path,
    trace_path: Path,
    baseline_path: Path,
    output_path: Path,
    update_baseline: bool,
    tolerance: float | None,
) -> None:
    """Evaluate RAG answers using curated datasets and guardrails."""

    records = _load_jsonl(dev_path) + _load_jsonl(trace_path)
    if not records:
        raise click.ClickException("No evaluation records were found.")

    needs_refresh = any(not record.contexts for record in records)
    if needs_refresh:
        engine = get_engine()
        with Session(engine) as session:
            for record in records:
                if not record.contexts:
                    _refresh_contexts(record, session)
    flatten_initial = _should_flatten_ground_truth()
    dataset = _build_dataset(records, flatten_ground_truth=flatten_initial)
    metrics = _build_metrics()
    if ragas_evaluate is None:
        raise click.ClickException(
            "ragas is not installed; cannot run evaluation."
        )
    evaluate_kwargs: dict[str, Any] = {"metrics": metrics, "in_ci": True}
    using_fake_models = False
    llm_override = _resolve_llm()
    if llm_override is not None:
        click.echo(
            "rag_eval: using deterministic fake LLM responses (no API key detected).",
            err=True,
        )
        if "llm" in inspect.signature(ragas_evaluate).parameters:
            evaluate_kwargs["llm"] = llm_override
        using_fake_models = True
    embeddings_override = _resolve_embeddings()
    if embeddings_override is not None:
        click.echo(
            "rag_eval: using fake embeddings (no API key detected).",
            err=True,
        )
        if "embeddings" in inspect.signature(ragas_evaluate).parameters:
            evaluate_kwargs["embeddings"] = embeddings_override
        using_fake_models = True
    try:
        result = ragas_evaluate(dataset, **evaluate_kwargs)
    except ValueError as exc:
        message = str(exc)
        if "ground_truth" in message and "type string" in message:
            click.echo(
                "rag_eval: flattening ground_truth lists for newer ragas releases.",
                err=True,
            )
            dataset = _build_dataset(records, flatten_ground_truth=True)
            result = ragas_evaluate(dataset, **evaluate_kwargs)
        else:
            raise

    metric_names = list(DEFAULT_THRESHOLDS.keys())
    overall_scores = _compute_overall_scores(result, metric_names)
    per_sample = _extract_per_sample_scores(result, records)

    baseline_scores, baseline_tolerance = _load_baseline(baseline_path)
    allowed_tolerance = tolerance if tolerance is not None else baseline_tolerance
    failing_rows: list[dict[str, Any]] = []
    for entry in per_sample:
        for metric, minimum in DEFAULT_THRESHOLDS.items():
            value = entry["scores"].get(metric)
            if value is None:
                continue
            if value < minimum:
                failing_rows.append(entry)
                break

    if failing_rows:
        click.echo("\n[warn] Low-scoring queries detected:")
        for entry in failing_rows:
            click.echo("\n" + "=" * 72)
            click.echo(f"Question: {entry['question']}")
            for metric in metric_names:
                score_value = entry["scores"].get(metric)
                click.echo(f"  - {metric}: {_format_score(score_value)}")
            if entry.get("citations"):
                click.echo("  Citations:")
                for citation in entry["citations"]:
                    osis = citation.get("osis", "?")
                    anchor = citation.get("anchor", "context")
                    snippet = citation.get("snippet", "")
                    click.echo(f"    - [{osis} {anchor}] {snippet}")
            if entry["contexts"]:
                click.echo("  Contexts:")
                for ctx in entry["contexts"]:
                    click.echo(f"    - {ctx}")

    regressions: list[dict[str, Any]] = []
    for metric, baseline_value in baseline_scores.items():
        current_value = overall_scores.get(metric)
        if current_value is None:
            continue
        if current_value + allowed_tolerance < baseline_value:
            regressions.append(
                {
                    "metric": metric,
                    "baseline": baseline_value,
                    "current": current_value,
                    "tolerance": allowed_tolerance,
                }
            )
    regression_messages = [
        f"{item['metric']} {item['current']:.3f} < {item['baseline']:.3f}"
        for item in regressions
    ]

    summary = {
        "overall": overall_scores,
        "per_sample": per_sample,
        "failing_rows": [entry["id"] for entry in failing_rows],
        "regressions": regressions,
        "baseline": baseline_scores,
        "tolerance": allowed_tolerance,
    }
    if using_fake_models:
        summary["notes"] = (
            "Evaluation ran with deterministic fake LLM/embeddings; metrics are"
            " informational only."
        )
    _write_summary(output_path, summary)
    issues: list[str] = []
    if failing_rows:
        issues.append("Low-scoring queries detected.")
    if regressions:
        regression_summary = "; ".join(regression_messages)
        issues.append(f"Metric regression detected: {regression_summary}")
    if issues:
        if using_fake_models:
            issues.append(
                "Evaluation ran with deterministic fake LLM/embeddings; rerun with"
                " production models to confirm."
            )
        raise click.ClickException(" ".join(issues))

    if update_baseline:
        _save_baseline(baseline_path, overall_scores, allowed_tolerance)
        click.echo(f"Baseline updated at {baseline_path}.")
        return

    click.echo("All metrics are within the configured tolerances.")


if __name__ == "__main__":  # pragma: no cover - manual invocation helper
    rag_eval()

