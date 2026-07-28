from __future__ import annotations

import math
import random
import statistics
from collections import Counter
from typing import Any

from intuition_map_private.store import PrivateWorkspace


def _wilson(successes: int, total: int, z: float = 1.96) -> list[float] | None:
    if total == 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            proportion * (1 - proportion) / total
            + z * z / (4 * total * total)
        )
        / denominator
    )
    return [max(0.0, center - margin), min(1.0, center + margin)]


def _median_bootstrap(
    values: list[float],
    *,
    seed: int = 1729,
    resamples: int = 2_000,
) -> list[float] | None:
    if not values:
        return None
    randomizer = random.Random(seed)
    samples = sorted(
        statistics.median(
            [randomizer.choice(values) for _ in values]
        )
        for _ in range(resamples)
    )
    lower = samples[math.floor(0.025 * (resamples - 1))]
    upper = samples[math.ceil(0.975 * (resamples - 1))]
    return [lower, upper]


def pilot_burden_summary(
    workspace: PrivateWorkspace,
    *,
    participant_id: str,
) -> dict[str, Any]:
    workspace.validate()
    with workspace.connect() as connection:
        exported = connection.execute(
            """
            SELECT
                i.item_id,
                i.stream,
                i.sampling_source,
                i.repeat_of_item_id,
                r.response_id,
                r.response_ms,
                r.skipped,
                r.verdict
            FROM annotation_items i
            LEFT JOIN annotation_responses r ON r.item_id=i.item_id
            WHERE i.participant_id=? AND i.exported_at IS NOT NULL
            """,
            (participant_id,),
        ).fetchall()
        original_verdicts = {
            row["item_id"]: row["verdict"]
            for row in exported
            if row["response_id"] is not None
            and row["repeat_of_item_id"] is None
            and not row["skipped"]
        }
    proposal_rows = [
        row
        for row in exported
        if row["stream"] == "proposal"
        and row["repeat_of_item_id"] is None
    ]
    discovery_rows = [
        row for row in exported if row["stream"] == "discovery"
    ]
    repeat_rows = [
        row for row in exported if row["repeat_of_item_id"] is not None
    ]
    completed_proposals = [
        row
        for row in proposal_rows
        if row["response_id"] is not None and not row["skipped"]
    ]
    completed_discovery = [
        row
        for row in discovery_rows
        if row["response_id"] is not None
    ]
    completed_repeats = [
        row
        for row in repeat_rows
        if row["response_id"] is not None and not row["skipped"]
    ]
    agreements = [
        int(row["verdict"] == original_verdicts[row["repeat_of_item_id"]])
        for row in completed_repeats
        if row["repeat_of_item_id"] in original_verdicts
    ]
    proposal_times = [
        row["response_ms"] / 1_000 for row in completed_proposals
    ]
    responded_rows = [
        row for row in exported if row["response_id"] is not None
    ]
    verdict_distribution = Counter(
        row["verdict"]
        for row in responded_rows
        if row["verdict"] is not None and not row["skipped"]
    )
    sampling_sources: dict[str, dict[str, int]] = {}
    for row in proposal_rows + repeat_rows:
        summary = sampling_sources.setdefault(
            row["sampling_source"],
            {"exported": 0, "responded": 0, "completed": 0, "skipped": 0},
        )
        summary["exported"] += 1
        if row["response_id"] is not None:
            summary["responded"] += 1
            if row["skipped"]:
                summary["skipped"] += 1
            else:
                summary["completed"] += 1
    proposal_completion = (
        len(completed_proposals) / len(proposal_rows)
        if proposal_rows
        else None
    )
    discovery_completion = (
        len(completed_discovery) / len(discovery_rows)
        if discovery_rows
        else None
    )
    repeat_agreement = (
        sum(agreements) / len(agreements) if agreements else None
    )
    evidence_minimums = {
        "completed_proposal_responses": len(completed_proposals) >= 100,
        "completed_discovery_prompts": len(completed_discovery) >= 20,
        "completed_blind_repeats": len(agreements) >= 10,
    }
    burden_thresholds = {
        "median_proposal_response_seconds": (
            bool(proposal_times) and statistics.median(proposal_times) <= 10
        ),
        "proposal_completion_rate": (
            proposal_completion is not None
            and proposal_completion >= 0.80
        ),
        "blind_repeat_exact_agreement": (
            repeat_agreement is not None and repeat_agreement >= 0.70
        ),
    }
    return {
        "schema_version": "0.1.0",
        "experiment_id": "EXP-P3-001",
        "counts": {
            "exported_proposals": len(proposal_rows),
            "completed_proposal_responses": len(completed_proposals),
            "exported_discovery_prompts": len(discovery_rows),
            "completed_discovery_prompts": len(completed_discovery),
            "exported_blind_repeats": len(repeat_rows),
            "completed_comparable_blind_repeats": len(agreements),
        },
        "metrics": {
            "median_proposal_response_seconds": (
                statistics.median(proposal_times)
                if proposal_times
                else None
            ),
            "median_response_time_bootstrap_95_interval": (
                _median_bootstrap(proposal_times)
            ),
            "proposal_completion_rate": proposal_completion,
            "proposal_completion_wilson_95_interval": _wilson(
                len(completed_proposals), len(proposal_rows)
            ),
            "discovery_completion_rate": discovery_completion,
            "discovery_completion_wilson_95_interval": _wilson(
                len(completed_discovery), len(discovery_rows)
            ),
            "blind_repeat_exact_agreement": repeat_agreement,
            "blind_repeat_agreement_wilson_95_interval": _wilson(
                sum(agreements), len(agreements)
            ),
            "skipped_item_rate": (
                sum(bool(row["skipped"]) for row in responded_rows)
                / len(responded_rows)
                if responded_rows
                else None
            ),
        },
        "verdict_distribution": dict(sorted(verdict_distribution.items())),
        "responses_by_sampling_source": dict(sorted(sampling_sources.items())),
        "minimum_evidence_passes": evidence_minimums,
        "burden_thresholds_pass": burden_thresholds,
        "all_burden_requirements_pass": (
            all(evidence_minimums.values())
            and all(burden_thresholds.values())
        ),
        "g3_pass": False,
        "g3_status": (
            "Safety, deletion, and provenance audits must also pass; this "
            "summary alone cannot mark G3 complete."
        ),
    }
