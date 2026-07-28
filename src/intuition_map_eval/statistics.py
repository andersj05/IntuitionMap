from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class PairedBootstrapResult:
    query_count: int
    resamples: int
    seed: int
    baseline_mean: float
    intervention_mean: float
    absolute_delta: float
    relative_delta: float | None
    confidence_level: float
    confidence_interval: tuple[float, float]

    def to_dict(self) -> dict[str, float | int | list[float] | None]:
        return {
            "query_count": self.query_count,
            "resamples": self.resamples,
            "seed": self.seed,
            "baseline_mean": self.baseline_mean,
            "intervention_mean": self.intervention_mean,
            "absolute_delta": self.absolute_delta,
            "relative_delta": self.relative_delta,
            "confidence_level": self.confidence_level,
            "confidence_interval": list(self.confidence_interval),
        }


def _percentile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("cannot take a percentile of no values")
    position = probability * (len(sorted_values) - 1)
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return sorted_values[lower_index]
    weight = position - lower_index
    return (
        sorted_values[lower_index] * (1.0 - weight)
        + sorted_values[upper_index] * weight
    )


def paired_query_bootstrap(
    baseline: Mapping[str, float],
    intervention: Mapping[str, float],
    *,
    resamples: int = 2_000,
    seed: int = 1729,
    confidence_level: float = 0.95,
) -> PairedBootstrapResult:
    if set(baseline) != set(intervention):
        missing_from_intervention = sorted(set(baseline) - set(intervention))
        missing_from_baseline = sorted(set(intervention) - set(baseline))
        raise ValueError(
            "paired bootstrap query ids differ; "
            f"missing_from_intervention={missing_from_intervention}, "
            f"missing_from_baseline={missing_from_baseline}"
        )
    if not baseline:
        raise ValueError("paired bootstrap requires at least one query")
    if isinstance(resamples, bool) or not isinstance(resamples, int) or resamples <= 0:
        raise ValueError("resamples must be a positive integer")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be between 0 and 1")
    query_ids = sorted(baseline)
    deltas: list[float] = []
    for query_id in query_ids:
        left = baseline[query_id]
        right = intervention[query_id]
        if not math.isfinite(left) or not math.isfinite(right):
            raise ValueError("paired bootstrap values must be finite")
        deltas.append(right - left)

    baseline_mean = sum(baseline.values()) / len(baseline)
    intervention_mean = sum(intervention.values()) / len(intervention)
    absolute_delta = intervention_mean - baseline_mean
    relative_delta = (
        absolute_delta / baseline_mean if baseline_mean != 0 else None
    )

    randomizer = random.Random(seed)
    bootstrap_deltas: list[float] = []
    for _ in range(resamples):
        bootstrap_deltas.append(
            sum(randomizer.choice(deltas) for _ in deltas) / len(deltas)
        )
    bootstrap_deltas.sort()
    alpha = (1.0 - confidence_level) / 2.0
    interval = (
        _percentile(bootstrap_deltas, alpha),
        _percentile(bootstrap_deltas, 1.0 - alpha),
    )
    return PairedBootstrapResult(
        query_count=len(query_ids),
        resamples=resamples,
        seed=seed,
        baseline_mean=baseline_mean,
        intervention_mean=intervention_mean,
        absolute_delta=absolute_delta,
        relative_delta=relative_delta,
        confidence_level=confidence_level,
        confidence_interval=interval,
    )
