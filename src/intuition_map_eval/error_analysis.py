from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from intuition_map_eval.baseline import Prediction, tokenize
from intuition_map_eval.dataset import Dataset
from intuition_map_eval.schema import Verdict


def analyze_retrieval_errors(
    dataset: Dataset,
    predictions: tuple[Prediction, ...],
    *,
    k: int = 5,
    generic_hub_rate: float = 0.75,
    generic_hub_min_queries: int = 3,
) -> dict[str, Any]:
    """Create deterministic screening codes for later human adjudication.

    Codes identify observable retrieval failures. They are not explanations of
    model intent and should not be treated as causal labels.
    """

    if isinstance(k, bool) or not isinstance(k, int) or k <= 0:
        raise ValueError("k must be a positive integer")
    if not 0 < generic_hub_rate <= 1:
        raise ValueError("generic_hub_rate must be in (0, 1]")
    ranked: dict[str, list[str]] = defaultdict(list)
    seen_pairs: set[tuple[str, str]] = set()
    for prediction in predictions:
        pair = (prediction.source_id, prediction.target_id)
        if pair in seen_pairs:
            raise ValueError(f"duplicate prediction for pair {pair}")
        seen_pairs.add(pair)
        ranked[prediction.source_id].append(prediction.target_id)
    for source_id in ranked:
        rows = sorted(
            (
                prediction
                for prediction in predictions
                if prediction.source_id == source_id
            ),
            key=lambda item: item.rank,
        )
        ranked[source_id] = [row.target_id for row in rows]

    top_counts: Counter[str] = Counter()
    eligible_counts: Counter[str] = Counter()
    for source in dataset.thoughts:
        top_counts.update(ranked.get(source.id, [])[:k])
        for target in dataset.thoughts:
            if target.created_at < source.created_at:
                eligible_counts[target.id] += 1
    hubs = {
        target_id
        for target_id, top_count in top_counts.items()
        if eligible_counts[target_id] >= generic_hub_min_queries
        and top_count / eligible_counts[target_id] >= generic_hub_rate
    }

    thoughts = dataset.thoughts_by_id
    rows: list[dict[str, Any]] = []
    for judgment in dataset.judgments:
        top_targets = ranked.get(judgment.source_id, [])[:k]
        if judgment.verdict.is_relevant and judgment.target_id not in top_targets:
            codes = [
                (
                    "MISSED_EXPLICIT"
                    if judgment.target_id
                    in thoughts[judgment.source_id].explicit_links
                    else "MISSED_ASSOCIATIVE"
                )
            ]
            if "tensions_with" in judgment.relation_types:
                codes.append("CONTRADICTION_MISSED")
            source_terms = tokenize(thoughts[judgment.source_id].text)
            target_terms = tokenize(thoughts[judgment.target_id].text)
            if not source_terms & target_terms:
                codes.append("OVERLY_SAFE")
            rows.append(
                {
                    "source_id": judgment.source_id,
                    "target_id": judgment.target_id,
                    "observed": "relevant judgment absent from top-k",
                    "codes": codes,
                    "rank": None,
                    "verdict": judgment.verdict.value,
                    "adjudication_required": True,
                }
            )
        if (
            judgment.verdict is Verdict.INVALID
            and judgment.target_id in top_targets
        ):
            source = thoughts[judgment.source_id]
            target = thoughts[judgment.target_id]
            codes: list[str] = []
            if (
                set(source.contexts).isdisjoint(target.contexts)
                and tokenize(source.text) & tokenize(target.text)
            ):
                codes.append("CONTEXT_COLLAPSE")
            if judgment.target_id in hubs:
                codes.append("GENERIC_HUB")
            rows.append(
                {
                    "source_id": judgment.source_id,
                    "target_id": judgment.target_id,
                    "observed": "known-invalid judgment exposed in top-k",
                    "codes": codes,
                    "rank": top_targets.index(judgment.target_id) + 1,
                    "verdict": judgment.verdict.value,
                    "adjudication_required": True,
                }
            )
    code_counts: Counter[str] = Counter(
        code for row in rows for code in row["codes"]
    )
    return {
        "schema_version": "0.1.0",
        "k": k,
        "screening_only": True,
        "rows": rows,
        "summary": {
            "error_row_count": len(rows),
            "code_counts": dict(sorted(code_counts.items())),
            "generic_hub_candidates": sorted(hubs),
        },
        "limitations": [
            "Unlabeled pairs remain unknown and are not errors.",
            "Context and hub codes are deterministic screening heuristics.",
            "Direction, relation, provenance, and graph-only failures require later task outputs.",
        ],
    }
