from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable

from intuition_map_eval.baseline import Prediction
from intuition_map_eval.dataset import Dataset
from intuition_map_eval.schema import LinkJudgment, Verdict


def _validate_predictions(
    dataset: Dataset, predictions: tuple[Prediction, ...]
) -> None:
    thoughts = dataset.thoughts_by_id
    ranks_by_source: dict[str, list[int]] = defaultdict(list)
    seen_pairs: set[tuple[str, str]] = set()
    for prediction in predictions:
        pair = (prediction.source_id, prediction.target_id)
        if pair in seen_pairs:
            raise ValueError(f"duplicate prediction for pair {pair}")
        seen_pairs.add(pair)
        if prediction.source_id not in thoughts:
            raise ValueError(f"prediction has unknown source: {prediction.source_id}")
        if prediction.target_id not in thoughts:
            raise ValueError(f"prediction has unknown target: {prediction.target_id}")
        if prediction.rank <= 0:
            raise ValueError("prediction ranks must be positive")
        if not math.isfinite(prediction.score):
            raise ValueError("prediction scores must be finite")
        source = thoughts[prediction.source_id]
        target = thoughts[prediction.target_id]
        if target.created_at >= source.created_at:
            raise ValueError(
                f"prediction temporal leakage: {target.id} does not predate {source.id}"
            )
        ranks_by_source[prediction.source_id].append(prediction.rank)
    for source_id, ranks in ranks_by_source.items():
        expected = list(range(1, len(ranks) + 1))
        if sorted(ranks) != expected:
            raise ValueError(
                f"prediction ranks for {source_id} must be contiguous from 1"
            )


def _macro_recall(
    source_ids: Iterable[str],
    gold: dict[str, set[str]],
    ranked: dict[str, list[str]],
    k: int,
) -> float | None:
    recalls: list[float] = []
    for source_id in source_ids:
        expected = gold.get(source_id, set())
        if not expected:
            continue
        predicted = set(ranked.get(source_id, [])[:k])
        recalls.append(len(expected & predicted) / len(expected))
    return sum(recalls) / len(recalls) if recalls else None


def _hit_rate(
    source_ids: Iterable[str],
    gold: dict[str, set[str]],
    ranked: dict[str, list[str]],
    k: int,
) -> float | None:
    hits: list[float] = []
    for source_id in source_ids:
        expected = gold.get(source_id, set())
        if not expected:
            continue
        predicted = set(ranked.get(source_id, [])[:k])
        hits.append(float(bool(expected & predicted)))
    return sum(hits) / len(hits) if hits else None


def compute_metrics(
    dataset: Dataset, predictions: tuple[Prediction, ...], top_k: list[int]
) -> dict[str, Any]:
    if not top_k or any(
        isinstance(k, bool) or not isinstance(k, int) or k <= 0 for k in top_k
    ):
        raise ValueError("top_k must contain positive integers")
    if len(top_k) != len(set(top_k)):
        raise ValueError("top_k values must be unique")
    _validate_predictions(dataset, predictions)

    ranked: dict[str, list[str]] = defaultdict(list)
    for prediction in sorted(predictions, key=lambda item: (item.source_id, item.rank)):
        ranked[prediction.source_id].append(prediction.target_id)

    judgments_by_pair: dict[tuple[str, str], LinkJudgment] = {
        (judgment.source_id, judgment.target_id): judgment
        for judgment in dataset.judgments
    }
    essential: dict[str, set[str]] = defaultdict(set)
    relevant: dict[str, set[str]] = defaultdict(set)
    judged_sources: set[str] = set()
    for judgment in dataset.judgments:
        judged_sources.add(judgment.source_id)
        if judgment.verdict is Verdict.ESSENTIAL:
            essential[judgment.source_id].add(judgment.target_id)
        if judgment.verdict.is_relevant:
            relevant[judgment.source_id].add(judgment.target_id)

    relevant_sources = sorted(relevant)
    reciprocal_ranks: list[float] = []
    for source_id in relevant_sources:
        relevant_targets = relevant[source_id]
        first_rank = next(
            (
                rank
                for rank, target_id in enumerate(ranked.get(source_id, []), start=1)
                if target_id in relevant_targets
            ),
            None,
        )
        reciprocal_ranks.append(0.0 if first_rank is None else 1.0 / first_rank)

    metrics_at_k: dict[str, Any] = {}
    for k in sorted(top_k):
        invalid_count = 0
        judged_prediction_count = 0
        invalid_counts_per_query: list[int] = []
        for source_id in sorted(judged_sources):
            query_invalid_count = 0
            for target_id in ranked.get(source_id, [])[:k]:
                judgment = judgments_by_pair.get((source_id, target_id))
                if judgment is None:
                    continue
                judged_prediction_count += 1
                if judgment.verdict is Verdict.INVALID:
                    invalid_count += 1
                    query_invalid_count += 1
            invalid_counts_per_query.append(query_invalid_count)
        metrics_at_k[str(k)] = {
            "essential_macro_recall": _macro_recall(
                sorted(essential), essential, ranked, k
            ),
            "relevant_macro_recall": _macro_recall(
                relevant_sources, relevant, ranked, k
            ),
            "relevant_hit_rate": _hit_rate(
                relevant_sources, relevant, ranked, k
            ),
            "known_invalid_predictions_per_judged_query": (
                sum(invalid_counts_per_query) / len(invalid_counts_per_query)
                if invalid_counts_per_query
                else None
            ),
            "invalid_rate_among_judged_predictions": (
                invalid_count / judged_prediction_count
                if judged_prediction_count
                else None
            ),
            "judged_prediction_count": judged_prediction_count,
        }

    verdict_counts: dict[str, int] = defaultdict(int)
    for judgment in dataset.judgments:
        verdict_counts[judgment.verdict.value] += 1

    return {
        "task": "temporal_edge_candidate_retrieval",
        "mean_reciprocal_rank": (
            sum(reciprocal_ranks) / len(reciprocal_ranks)
            if reciprocal_ranks
            else None
        ),
        "at_k": metrics_at_k,
        "coverage": {
            "thought_count": len(dataset.thoughts),
            "possible_source_thought_count": len(dataset.thoughts) - 1,
            "sources_with_judgments": len(judged_sources),
            "sources_with_relevant_judgments": len(relevant_sources),
            "judgment_count": len(dataset.judgments),
            "judgment_counts": dict(sorted(verdict_counts.items())),
            "annotation_exhaustive": dataset.manifest.annotation.exhaustive,
        },
    }
