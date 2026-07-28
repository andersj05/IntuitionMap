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
        if prediction.confidence is not None:
            if (
                isinstance(prediction.confidence, bool)
                or not isinstance(prediction.confidence, (int, float))
                or not math.isfinite(prediction.confidence)
                or not 0.0 <= prediction.confidence <= 1.0
            ):
                raise ValueError(
                    "prediction confidence must be finite and between 0 and 1"
                )
        if prediction.abstained is not None and not isinstance(
            prediction.abstained, bool
        ):
            raise ValueError("prediction abstained must be a boolean")
        if prediction.method is not None and (
            not isinstance(prediction.method, str)
            or not prediction.method.strip()
        ):
            raise ValueError("prediction method must be a non-empty string")
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


def _dcg(gains: list[float]) -> float:
    return sum(
        gain / math.log2(rank + 1)
        for rank, gain in enumerate(gains, start=1)
    )


def _judged_graded_ndcg(
    source_id: str,
    ranked: dict[str, list[str]],
    judgments_by_pair: dict[tuple[str, str], LinkJudgment],
    judgments_by_source: dict[str, list[LinkJudgment]],
    k: int,
) -> float | None:
    gain_by_verdict = {
        Verdict.ESSENTIAL: 3.0,
        Verdict.VALID: 1.0,
        Verdict.INVALID: 0.0,
        Verdict.UNCERTAIN: 0.0,
    }
    ideal_gains = sorted(
        (
            gain_by_verdict[judgment.verdict]
            for judgment in judgments_by_source.get(source_id, [])
        ),
        reverse=True,
    )[:k]
    ideal = _dcg(ideal_gains)
    if ideal == 0:
        return None
    observed_gains = [
        gain_by_verdict[judgments_by_pair[(source_id, target_id)].verdict]
        if (source_id, target_id) in judgments_by_pair
        else 0.0
        for target_id in ranked.get(source_id, [])[:k]
    ]
    return _dcg(observed_gains) / ideal


def _mean(values: Iterable[float | None]) -> float | None:
    observed = [value for value in values if value is not None]
    return sum(observed) / len(observed) if observed else None


def _time_distance_bucket(days: float) -> str:
    if days <= 7:
        return "0-7d"
    if days <= 30:
        return "8-30d"
    if days <= 180:
        return "31-180d"
    return "181d+"


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
    judgments_by_source: dict[str, list[LinkJudgment]] = defaultdict(list)
    essential: dict[str, set[str]] = defaultdict(set)
    relevant: dict[str, set[str]] = defaultdict(set)
    judged_sources: set[str] = set()
    for judgment in dataset.judgments:
        judgments_by_source[judgment.source_id].append(judgment)
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

    per_query: dict[str, Any] = {}
    for source_id in sorted(judged_sources):
        relevant_targets = relevant.get(source_id, set())
        first_rank = next(
            (
                rank
                for rank, target_id in enumerate(
                    ranked.get(source_id, []), start=1
                )
                if target_id in relevant_targets
            ),
            None,
        )
        per_query[source_id] = {
            "judgment_count": len(judgments_by_source[source_id]),
            "relevant_judgment_count": len(relevant_targets),
            "reciprocal_rank": (
                0.0
                if relevant_targets and first_rank is None
                else (1.0 / first_rank if first_rank is not None else None)
            ),
            "at_k": {},
        }

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
            relevant_targets = relevant.get(source_id, set())
            essential_targets = essential.get(source_id, set())
            predicted = set(ranked.get(source_id, [])[:k])
            per_query[source_id]["at_k"][str(k)] = {
                "essential_recall": (
                    len(essential_targets & predicted) / len(essential_targets)
                    if essential_targets
                    else None
                ),
                "relevant_recall": (
                    len(relevant_targets & predicted) / len(relevant_targets)
                    if relevant_targets
                    else None
                ),
                "relevant_hit": (
                    float(bool(relevant_targets & predicted))
                    if relevant_targets
                    else None
                ),
                "judged_graded_ndcg_lower_bound": _judged_graded_ndcg(
                    source_id,
                    ranked,
                    judgments_by_pair,
                    judgments_by_source,
                    k,
                ),
                "known_invalid_predictions": query_invalid_count,
            }
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
            "judged_graded_ndcg_lower_bound": _mean(
                per_query[source_id]["at_k"][str(k)][
                    "judged_graded_ndcg_lower_bound"
                ]
                for source_id in sorted(judged_sources)
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

    relation_gold: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    time_gold: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for judgment in dataset.judgments:
        if not judgment.verdict.is_relevant:
            continue
        for relation_type in judgment.relation_types:
            relation_gold[relation_type][judgment.source_id].add(
                judgment.target_id
            )
        source = dataset.thoughts_by_id[judgment.source_id]
        target = dataset.thoughts_by_id[judgment.target_id]
        age_days = (source.created_at - target.created_at).total_seconds() / 86_400
        time_gold[_time_distance_bucket(age_days)][judgment.source_id].add(
            judgment.target_id
        )

    def subgroup_report(
        groups: dict[str, dict[str, set[str]]],
    ) -> dict[str, Any]:
        report: dict[str, Any] = {}
        for group, gold in sorted(groups.items()):
            source_ids = sorted(gold)
            report[group] = {
                "source_count": len(source_ids),
                "relevant_judgment_count": sum(map(len, gold.values())),
                "relevant_macro_recall_at_k": {
                    str(k): _macro_recall(source_ids, gold, ranked, k)
                    for k in sorted(top_k)
                },
            }
        return report

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
        "per_query": per_query,
        "subgroups": {
            "relation_type": subgroup_report(relation_gold),
            "time_distance": subgroup_report(time_gold),
        },
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
