from __future__ import annotations

import json
import platform
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intuition_map_eval import __version__
from intuition_map_eval.baseline import (
    LexicalTemporalBaseline,
    LexicalTemporalConfig,
    Prediction,
)
from intuition_map_eval.dataset import Dataset, load_dataset
from intuition_map_eval.error_analysis import analyze_retrieval_errors
from intuition_map_eval.fingerprint import canonical_text_sha256
from intuition_map_eval.metrics import compute_metrics
from intuition_map_models.retrieval import (
    BM25Ranker,
    ExplicitLinkRanker,
    HashedEmbeddingRanker,
    MostRecentRanker,
    Ranker,
    ReciprocalRankFusionRanker,
    StableRandomRanker,
    TfIdfRanker,
    rank_dataset,
)


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    raw: dict[str, Any]
    schema_version: str
    name: str
    seed: int
    candidate_generator_type: str
    candidate_generator_parameters: dict[str, Any]
    top_k: list[int]
    budget: dict[str, Any]


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing configuration file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}:{exc.lineno}: invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    path = Path(path).resolve()
    data = _read_json_object(path)
    required = {
        "schema_version",
        "name",
        "seed",
        "candidate_generator",
        "evaluation",
        "budget",
    }
    missing = required - data.keys()
    unknown = data.keys() - required
    if missing:
        raise ValueError(f"experiment config is missing fields: {sorted(missing)}")
    if unknown:
        raise ValueError(f"experiment config has unknown fields: {sorted(unknown)}")
    if data["schema_version"] not in {"0.1.0", "0.2.0"}:
        raise ValueError("unsupported experiment schema_version")
    if not isinstance(data["name"], str) or not data["name"].strip():
        raise ValueError("experiment name must be a non-empty string")
    if isinstance(data["seed"], bool) or not isinstance(data["seed"], int):
        raise ValueError("seed must be an integer")

    generator = data["candidate_generator"]
    if not isinstance(generator, dict):
        raise ValueError("candidate_generator must be an object")
    if set(generator) != {"type", "parameters"}:
        raise ValueError(
            "candidate_generator must contain only type and parameters"
        )
    supported_generators = {
        "lexical_temporal",
        "stable_random",
        "most_recent",
        "tfidf",
        "bm25",
        "explicit_link",
        "hashed_embedding",
        "rrf_hybrid",
    }
    if generator["type"] not in supported_generators:
        raise ValueError(
            "candidate_generator.type must be one of "
            f"{sorted(supported_generators)}"
        )
    if (
        data["schema_version"] == "0.1.0"
        and generator["type"] != "lexical_temporal"
    ):
        raise ValueError(
            "experiment schema_version 0.1.0 supports only lexical_temporal"
        )
    if not isinstance(generator["parameters"], dict):
        raise ValueError("candidate_generator.parameters must be an object")

    evaluation = data["evaluation"]
    if not isinstance(evaluation, dict) or set(evaluation) != {"top_k"}:
        raise ValueError("evaluation must contain only top_k")
    top_k = evaluation["top_k"]
    if (
        not isinstance(top_k, list)
        or not top_k
        or any(isinstance(k, bool) or not isinstance(k, int) or k <= 0 for k in top_k)
        or len(top_k) != len(set(top_k))
    ):
        raise ValueError("evaluation.top_k must contain unique positive integers")

    budget = data["budget"]
    budget_fields = {
        "allow_paid_api",
        "max_cost_usd",
        "max_output_tokens_per_request",
        "max_paid_retries",
    }
    if not isinstance(budget, dict) or set(budget) != budget_fields:
        raise ValueError(
            f"budget must contain exactly {sorted(budget_fields)}"
        )
    if not isinstance(budget["allow_paid_api"], bool):
        raise ValueError("budget.allow_paid_api must be a boolean")
    if (
        isinstance(budget["max_cost_usd"], bool)
        or not isinstance(budget["max_cost_usd"], (int, float))
        or budget["max_cost_usd"] < 0
    ):
        raise ValueError("budget.max_cost_usd must be a non-negative number")
    if data["schema_version"] == "0.1.0" and budget["max_cost_usd"] == 0:
        raise ValueError(
            "budget.max_cost_usd must be positive in schema version 0.1.0"
        )
    if budget["allow_paid_api"] and budget["max_cost_usd"] == 0:
        raise ValueError(
            "a paid experiment must have a positive max_cost_usd"
        )
    if (
        isinstance(budget["max_output_tokens_per_request"], bool)
        or not isinstance(budget["max_output_tokens_per_request"], int)
        or budget["max_output_tokens_per_request"] <= 0
    ):
        raise ValueError(
            "budget.max_output_tokens_per_request must be a positive integer"
        )
    if budget["max_paid_retries"] != 0:
        raise ValueError("max_paid_retries must remain 0 in schema version 0.1.0")

    config = ExperimentConfig(
        raw=data,
        schema_version=data["schema_version"],
        name=data["name"].strip(),
        seed=data["seed"],
        candidate_generator_type=generator["type"],
        candidate_generator_parameters=dict(generator["parameters"]),
        top_k=sorted(top_k),
        budget=budget,
    )
    if config.candidate_generator_type == "lexical_temporal":
        LexicalTemporalConfig.from_dict(
            config.candidate_generator_parameters
        )
    else:
        _build_ranker(config)
    return config


def _number(
    parameters: dict[str, Any],
    field: str,
    default: float,
) -> float:
    value = parameters.pop(field, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    return float(value)


def _integer(
    parameters: dict[str, Any],
    field: str,
    default: int,
) -> int:
    value = parameters.pop(field, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def _require_no_parameters(
    generator_type: str, parameters: dict[str, Any]
) -> None:
    if parameters:
        raise ValueError(
            f"unknown {generator_type} parameters: {sorted(parameters)}"
        )


def _build_ranker(config: ExperimentConfig) -> Ranker:
    generator_type = config.candidate_generator_type
    parameters = dict(config.candidate_generator_parameters)
    if generator_type == "stable_random":
        _require_no_parameters(generator_type, parameters)
        return StableRandomRanker(config.seed)
    if generator_type == "most_recent":
        _require_no_parameters(generator_type, parameters)
        return MostRecentRanker()
    if generator_type == "tfidf":
        _require_no_parameters(generator_type, parameters)
        return TfIdfRanker()
    if generator_type == "bm25":
        k1 = _number(parameters, "k1", 1.2)
        b = _number(parameters, "b", 0.75)
        _require_no_parameters(generator_type, parameters)
        return BM25Ranker(k1=k1, b=b)
    if generator_type == "explicit_link":
        _require_no_parameters(generator_type, parameters)
        return ExplicitLinkRanker()
    if generator_type == "hashed_embedding":
        dimensions = _integer(parameters, "dimensions", 512)
        _require_no_parameters(generator_type, parameters)
        return HashedEmbeddingRanker(
            dimensions=dimensions,
            seed=config.seed,
        )
    if generator_type == "rrf_hybrid":
        dimensions = _integer(parameters, "dimensions", 512)
        rrf_k = _integer(parameters, "rrf_k", 60)
        k1 = _number(parameters, "bm25_k1", 1.2)
        b = _number(parameters, "bm25_b", 0.75)
        _require_no_parameters(generator_type, parameters)
        return ReciprocalRankFusionRanker(
            (
                BM25Ranker(k1=k1, b=b),
                HashedEmbeddingRanker(
                    dimensions=dimensions,
                    seed=config.seed,
                ),
                MostRecentRanker(),
            ),
            rrf_k=rrf_k,
        )
    raise ValueError(f"{generator_type} does not use the generic ranker")


def _file_sha256(path: Path) -> str:
    return canonical_text_sha256(path)


def _git_metadata(repo_root: Path) -> dict[str, Any]:
    safe_arg = f"safe.directory={repo_root.as_posix()}"

    def run_git(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-c", safe_arg, *arguments],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

    revision = run_git("rev-parse", "HEAD")
    status = run_git("status", "--porcelain")
    return {
        "revision": revision.stdout.strip() if revision.returncode == 0 else None,
        "dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
    }


def _prediction_rows(
    dataset: Dataset, predictions: tuple[Prediction, ...]
) -> list[dict[str, Any]]:
    judgments = {
        (judgment.source_id, judgment.target_id): judgment
        for judgment in dataset.judgments
    }
    rows: list[dict[str, Any]] = []
    for prediction in predictions:
        row = prediction.to_dict()
        judgment = judgments.get((prediction.source_id, prediction.target_id))
        row["judgment"] = judgment.to_dict() if judgment else None
        rows.append(row)
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")))
            handle.write("\n")


def run_experiment(
    *,
    dataset_path: str | Path,
    config_path: str | Path,
    output_root: str | Path,
    cli_allows_paid_api: bool = False,
) -> tuple[Path, dict[str, Any]]:
    started = time.perf_counter()
    dataset = load_dataset(dataset_path)
    config_path = Path(config_path).resolve()
    config = load_experiment_config(config_path)

    if config.candidate_generator_type == "lexical_temporal":
        baseline = LexicalTemporalBaseline(
            LexicalTemporalConfig.from_dict(
                config.candidate_generator_parameters
            )
        )
        predictions = baseline.rank(dataset)
    else:
        predictions = rank_dataset(dataset, _build_ranker(config))
    metrics = compute_metrics(dataset, predictions, config.top_k)
    elapsed_seconds = time.perf_counter() - started
    metrics["runtime"] = {
        "wall_seconds": elapsed_seconds,
        "paid_api_request_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost_usd": "0",
    }

    now = datetime.now(timezone.utc)
    run_id = f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-{config.name}"
    output_root = Path(output_root).resolve()
    run_path = output_root / run_id
    run_path.mkdir(parents=True, exist_ok=False)

    repo_root = config_path.parent.parent
    manifest = {
        "schema_version": config.schema_version,
        "harness_version": __version__,
        "run_id": run_id,
        "created_at": now.isoformat().replace("+00:00", "Z"),
        "task": "temporal_edge_candidate_retrieval",
        "dataset": {
            "name": dataset.manifest.name,
            "fingerprint": dataset.fingerprint,
            "annotation_exhaustive": dataset.manifest.annotation.exhaustive,
        },
        "experiment": {
            "name": config.name,
            "config_sha256": _file_sha256(config_path),
            "seed": config.seed,
        },
        "source": {
            **_git_metadata(repo_root),
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "spend_controls": {
            **config.budget,
            "cli_allows_paid_api": cli_allows_paid_api,
            "paid_api_used": False,
        },
    }

    _write_json(run_path / "manifest.json", manifest)
    _write_json(run_path / "config.resolved.json", config.raw)
    _write_json(run_path / "metrics.json", metrics)
    _write_json(
        run_path / "error-analysis.json",
        analyze_retrieval_errors(
            dataset,
            predictions,
            k=max(config.top_k),
        ),
    )
    _write_json(
        run_path / "usage.json",
        {
            "paid_api_request_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "estimated_cost_usd": "0",
            "records": [],
        },
    )
    _write_jsonl(
        run_path / "predictions.jsonl",
        _prediction_rows(dataset, predictions),
    )
    return run_path, metrics
