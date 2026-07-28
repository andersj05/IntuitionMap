from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intuition_map_data.adapters.longmemeval import (
    LongMemEvalRecord,
    iter_longmemeval,
)
from intuition_map_eval.dataset import load_dataset
from intuition_map_eval.metrics import compute_metrics
from intuition_map_eval.statistics import paired_query_bootstrap
from intuition_map_models.retrieval import (
    BM25Ranker,
    HashedEmbeddingRanker,
    MostRecentRanker,
    Ranker,
    ReciprocalRankFusionRanker,
    RetrievalCandidate,
    RetrievalQuery,
    StableRandomRanker,
    TfIdfRanker,
    rank_dataset,
)

DEFAULT_METHODS = (
    "stable_random",
    "most_recent",
    "tfidf",
    "bm25",
    "hashed_embedding",
    "rrf_hybrid",
)


def parse_native_datetime(value: str) -> datetime:
    try:
        date_part, time_part = value.split(") ", maxsplit=1)
        normalized = f"{date_part.split(' (', maxsplit=1)[0]} {time_part}"
        parsed = datetime.strptime(normalized, "%Y/%m/%d %H:%M")
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"unsupported LongMemEval datetime: {value!r}"
        ) from exc
    return parsed.replace(tzinfo=timezone.utc)


def retrieval_view(
    record: LongMemEvalRecord,
) -> tuple[RetrievalQuery, frozenset[str]]:
    candidates: list[RetrievalCandidate] = []
    for session in record.sessions:
        session_time = parse_native_datetime(session.date)
        text = "\n".join(
            f"{turn.role}: {turn.content}"
            for turn in session.turns
            if not turn.is_empty
        )
        candidates.append(
            RetrievalCandidate(
                candidate_id=session.candidate_id,
                native_id=session.session_id,
                text=text,
                order=session.position,
                timestamp=session_time,
            )
        )
    evidence_native_ids = set(record.answer_session_ids)
    collision_counts: dict[str, int] = defaultdict(int)
    for candidate in candidates:
        if candidate.native_id in evidence_native_ids:
            collision_counts[candidate.native_id] += 1
    ambiguous = sorted(
        native_id for native_id, count in collision_counts.items() if count > 1
    )
    if ambiguous:
        raise ValueError(
            f"LongMemEval evidence ids are ambiguous in {record.question_id}: "
            f"{ambiguous}"
        )
    gold = frozenset(
        candidate.candidate_id
        for candidate in candidates
        if candidate.native_id in evidence_native_ids
    )
    if not gold:
        raise ValueError(
            f"LongMemEval query {record.question_id} has no evidence candidate"
        )
    return (
        RetrievalQuery(
            query_id=record.question_id,
            text=record.question,
            candidates=tuple(candidates),
        ),
        gold,
    )


def native_timestamp_audit(record: LongMemEvalRecord) -> dict[str, int]:
    """Audit wall-clock anomalies without redefining native availability.

    LongMemEval states that the question is asked after the supplied history.
    Some cleaned records nevertheless have session timestamps at or after
    ``question_date``. The native history envelope therefore determines
    availability for this benchmark; strict capture-time checks remain
    mandatory for IntuitionMap data.
    """

    question_time = parse_native_datetime(record.question_date)
    evidence = set(record.answer_session_ids)
    result = {
        "session_before_question_date": 0,
        "session_equal_question_date": 0,
        "session_after_question_date": 0,
        "evidence_equal_question_date": 0,
        "evidence_after_question_date": 0,
    }
    for session in record.sessions:
        session_time = parse_native_datetime(session.date)
        if session_time < question_time:
            result["session_before_question_date"] += 1
        elif session_time == question_time:
            result["session_equal_question_date"] += 1
            result["evidence_equal_question_date"] += int(
                session.session_id in evidence
            )
        else:
            result["session_after_question_date"] += 1
            result["evidence_after_question_date"] += int(
                session.session_id in evidence
            )
    return result


def _dcg(gains: list[float]) -> float:
    return sum(
        gain / math.log2(rank + 1)
        for rank, gain in enumerate(gains, start=1)
    )


def score_query(
    ranked_ids: list[str],
    gold_ids: frozenset[str],
    top_k: tuple[int, ...],
) -> dict[str, Any]:
    first_rank = next(
        (
            rank
            for rank, candidate_id in enumerate(ranked_ids, start=1)
            if candidate_id in gold_ids
        ),
        None,
    )
    result: dict[str, Any] = {
        "reciprocal_rank": 0.0 if first_rank is None else 1.0 / first_rank,
        "at_k": {},
    }
    for k in top_k:
        selected = ranked_ids[:k]
        found = len(set(selected) & gold_ids)
        ideal = _dcg([1.0] * min(len(gold_ids), k))
        observed = _dcg(
            [float(candidate_id in gold_ids) for candidate_id in selected]
        )
        result["at_k"][str(k)] = {
            "evidence_recall": found / len(gold_ids),
            "evidence_hit": float(found > 0),
            "binary_ndcg": observed / ideal,
        }
    return result


def _percentile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _aggregate_method(
    per_query: dict[str, dict[str, Any]],
    query_types: dict[str, str],
    latencies: list[float],
    top_k: tuple[int, ...],
) -> dict[str, Any]:
    aggregate_at_k: dict[str, Any] = {}
    for k in top_k:
        aggregate_at_k[str(k)] = {
            metric: _mean(
                [
                    result["at_k"][str(k)][metric]
                    for result in per_query.values()
                ]
            )
            for metric in ("evidence_recall", "evidence_hit", "binary_ndcg")
        }
    subgroup: dict[str, Any] = {}
    for question_type in sorted(set(query_types.values())):
        query_ids = sorted(
            query_id
            for query_id, value in query_types.items()
            if value == question_type
        )
        subgroup[question_type] = {
            "query_count": len(query_ids),
            "at_k": {
                str(k): {
                    "evidence_recall": _mean(
                        [
                            per_query[query_id]["at_k"][str(k)][
                                "evidence_recall"
                            ]
                            for query_id in query_ids
                        ]
                    ),
                    "evidence_hit": _mean(
                        [
                            per_query[query_id]["at_k"][str(k)][
                                "evidence_hit"
                            ]
                            for query_id in query_ids
                        ]
                    ),
                }
                for k in top_k
            },
        }
    return {
        "query_count": len(per_query),
        "mean_reciprocal_rank": _mean(
            [result["reciprocal_rank"] for result in per_query.values()]
        ),
        "at_k": aggregate_at_k,
        "latency_ms": {
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
        },
        "serialized_index_bytes": 0,
        "subgroups": {"question_type": subgroup},
        "per_query": per_query,
    }


def _rankers(seed: int) -> dict[str, Ranker]:
    bm25 = BM25Ranker(k1=1.2, b=0.75)
    embedding = HashedEmbeddingRanker(dimensions=512, seed=seed)
    recency = MostRecentRanker()
    return {
        "stable_random": StableRandomRanker(seed),
        "most_recent": recency,
        "tfidf": TfIdfRanker(),
        "bm25": bm25,
        "hashed_embedding": embedding,
        "rrf_hybrid": ReciprocalRankFusionRanker(
            (bm25, embedding, recency), rrf_k=60
        ),
    }


def _comparison(
    baseline_name: str,
    intervention_name: str,
    methods: dict[str, Any],
    *,
    top_k: int,
    seed: int,
) -> dict[str, Any]:
    baseline = {
        query_id: result["at_k"][str(top_k)]["evidence_recall"]
        for query_id, result in methods[baseline_name]["per_query"].items()
    }
    intervention = {
        query_id: result["at_k"][str(top_k)]["evidence_recall"]
        for query_id, result in methods[intervention_name]["per_query"].items()
    }
    bootstrap = paired_query_bootstrap(
        baseline,
        intervention,
        resamples=2_000,
        seed=seed,
    )
    effect_passes = (
        bootstrap.absolute_delta >= 0.05
        or (
            bootstrap.relative_delta is not None
            and bootstrap.relative_delta >= 0.10
        )
    )
    interval_excludes_zero = (
        bootstrap.confidence_interval[0] > 0
        or bootstrap.confidence_interval[1] < 0
    )
    interval_favors_intervention = bootstrap.confidence_interval[0] > 0
    return {
        "baseline": baseline_name,
        "intervention": intervention_name,
        "metric": f"macro_evidence_recall_at_{top_k}",
        **bootstrap.to_dict(),
        "minimum_effect_passes": effect_passes,
        "confidence_interval_excludes_zero": interval_excludes_zero,
        "confidence_interval_favors_intervention": (
            interval_favors_intervention
        ),
        "retrieval_effect_passes": (
            effect_passes and interval_favors_intervention
        ),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_longmemeval_benchmark(
    *,
    artifact_path: str | Path,
    smoke_dataset_path: str | Path,
    output_path: str | Path,
    seed: int = 1729,
    top_k: tuple[int, ...] = (1, 3, 5, 10),
    progress_every: int = 50,
) -> dict[str, Any]:
    if not top_k or any(k <= 0 for k in top_k):
        raise ValueError("top_k must contain positive integers")
    artifact_path = Path(artifact_path).resolve()
    output_path = Path(output_path).resolve()
    rankers = _rankers(seed)
    per_method: dict[str, dict[str, dict[str, Any]]] = {
        name: {} for name in rankers
    }
    latencies: dict[str, list[float]] = {
        name: [] for name in rankers
    }
    query_types: dict[str, str] = {}
    top_prediction_rows: dict[str, list[dict[str, Any]]] = {
        name: [] for name in rankers
    }
    started = time.perf_counter()
    record_count = 0
    evaluated_query_count = 0
    excluded_abstention_count = 0
    timestamp_audit = {
        "session_before_question_date": 0,
        "session_equal_question_date": 0,
        "session_after_question_date": 0,
        "evidence_equal_question_date": 0,
        "evidence_after_question_date": 0,
    }
    for record_count, record in enumerate(
        iter_longmemeval(artifact_path), start=1
    ):
        for key, value in native_timestamp_audit(record).items():
            timestamp_audit[key] += value
        if record.question_id.endswith("_abs"):
            excluded_abstention_count += 1
            continue
        evaluated_query_count += 1
        query, gold = retrieval_view(record)
        query_types[query.query_id] = record.question_type
        query_rankings: dict[str, tuple[Any, ...]] = {}
        query_latencies: dict[str, float] = {}
        for method, ranker in rankers.items():
            if method == "rrf_hybrid":
                continue
            query_started = time.perf_counter()
            ranking = ranker.rank(query)
            query_latencies[method] = (
                time.perf_counter() - query_started
            ) * 1_000
            query_rankings[method] = ranking
        fusion = rankers["rrf_hybrid"]
        if not isinstance(fusion, ReciprocalRankFusionRanker):
            raise RuntimeError("rrf_hybrid ranker has the wrong type")
        fusion_started = time.perf_counter()
        query_rankings["rrf_hybrid"] = fusion.fuse(
            query,
            {
                "bm25": query_rankings["bm25"],
                "hashed_embedding": query_rankings["hashed_embedding"],
                "most_recent": query_rankings["most_recent"],
            },
        )
        fusion_latency = (time.perf_counter() - fusion_started) * 1_000
        query_latencies["rrf_hybrid"] = (
            query_latencies["bm25"]
            + query_latencies["hashed_embedding"]
            + query_latencies["most_recent"]
            + fusion_latency
        )
        for method, ranking in query_rankings.items():
            latencies[method].append(query_latencies[method])
            ranked_ids = [item.candidate_id for item in ranking]
            per_method[method][query.query_id] = score_query(
                ranked_ids, gold, top_k
            )
            top_prediction_rows[method].append(
                {
                    "query_id": query.query_id,
                    "gold_candidate_ids": sorted(gold),
                    "top_10": [
                        {
                            "candidate_id": item.candidate_id,
                            "rank": item.rank,
                            "score": item.score,
                        }
                        for item in ranking[:10]
                    ],
                }
            )
        if progress_every and evaluated_query_count % progress_every == 0:
            print(
                f"evaluated {evaluated_query_count} LongMemEval-S queries",
                file=sys.stderr,
                flush=True,
            )
    if record_count == 0:
        raise ValueError("LongMemEval artifact contains no records")

    methods = {
        method: _aggregate_method(
            results, query_types, latencies[method], top_k
        )
        for method, results in per_method.items()
    }
    cheap_controls = ("stable_random", "most_recent", "tfidf")
    strongest_cheap = max(
        cheap_controls,
        key=lambda name: methods[name]["at_k"]["10"]["evidence_recall"],
    )
    comparison_bm25 = _comparison(
        strongest_cheap, "bm25", methods, top_k=10, seed=seed
    )
    comparison_hybrid = _comparison(
        "bm25", "rrf_hybrid", methods, top_k=10, seed=seed
    )

    smoke_dataset = load_dataset(smoke_dataset_path)
    smoke_invalid_exposure = {}
    for method, ranker in rankers.items():
        smoke_metrics = compute_metrics(
            smoke_dataset, rank_dataset(smoke_dataset, ranker), [5]
        )
        smoke_invalid_exposure[method] = smoke_metrics["at_k"]["5"][
            "known_invalid_predictions_per_judged_query"
        ]
    bm25_tolerance = (
        smoke_invalid_exposure["bm25"]
        - smoke_invalid_exposure[strongest_cheap]
        <= 0.10
    )
    hybrid_tolerance = (
        smoke_invalid_exposure["rrf_hybrid"]
        - smoke_invalid_exposure["bm25"]
        <= 0.10
    )
    comparison_bm25["smoke_invalid_exposure_tolerance_passes"] = bm25_tolerance
    comparison_hybrid[
        "smoke_invalid_exposure_tolerance_passes"
    ] = hybrid_tolerance
    comparison_bm25["overall_preregistered_rule_passes"] = (
        comparison_bm25["retrieval_effect_passes"] and bm25_tolerance
    )
    comparison_hybrid["overall_preregistered_rule_passes"] = (
        comparison_hybrid["retrieval_effect_passes"] and hybrid_tolerance
    )

    result = {
        "schema_version": "0.1.0",
        "benchmark": "LongMemEval-S evidence-session retrieval",
        "created_at": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "input": {
            "path": str(artifact_path),
            "sha256": _sha256_file(artifact_path),
            "native_query_count": record_count,
            "evaluated_query_count": evaluated_query_count,
            "excluded_abstention_query_count": excluded_abstention_count,
        },
        "protocol": {
            "seed": seed,
            "top_k": list(top_k),
            "information_access": (
                "question plus every session in the native history envelope"
            ),
            "answers_or_evidence_visible_to_rankers": False,
            "availability_rule": (
                "The official benchmark states that each question follows all "
                "supplied history. Native envelope membership, not comparison "
                "with question_date, defines availability."
            ),
            "retrieval_exclusions": (
                "Question ids ending _abs are excluded per the official "
                "retrieval protocol."
            ),
            "native_timestamp_audit": timestamp_audit,
            "empty_native_turns_preserved": True,
            "explicit_link_control": {
                "status": "not-applicable",
                "reason": "LongMemEval has evidence labels, not user-authored explicit links.",
            },
        },
        "methods": methods,
        "comparisons": {
            "EXP-P2-001": comparison_bm25,
            "EXP-P2-002": comparison_hybrid,
        },
        "smoke_known_invalid_predictions_per_judged_query_at_5": (
            smoke_invalid_exposure
        ),
        "runtime": {
            "wall_seconds": time.perf_counter() - started,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "paid_api_request_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "estimated_cost_usd": "0",
        },
        "claims": {
            "supports": ["C2 generic temporal-memory retrieval capability"],
            "does_not_support": [
                "C3 personal associative fidelity",
                "invalid-link control on LongMemEval",
            ],
        },
        "top_10_predictions": top_prediction_rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the zero-cost LongMemEval-S retrieval ablation."
    )
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument(
        "--smoke-dataset", default=Path("datasets/smoke"), type=Path
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", default=1729, type=int)
    args = parser.parse_args(argv)
    result = run_longmemeval_benchmark(
        artifact_path=args.artifact,
        smoke_dataset_path=args.smoke_dataset,
        output_path=args.output,
        seed=args.seed,
    )
    summary = {
        "output": str(args.output.resolve()),
        "comparisons": result["comparisons"],
        "runtime": result["runtime"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
