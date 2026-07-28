from __future__ import annotations

import json
import unittest
from pathlib import Path

from intuition_map_data.adapters.longmemeval import (
    LongMemEvalRecord,
    iter_longmemeval,
)
from intuition_map_eval.longmemeval_benchmark import (
    _comparison,
    native_timestamp_audit,
    retrieval_view,
    score_query,
)
from intuition_map_models.retrieval import BM25Ranker

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "public"
    / "longmemeval-mini.json"
)


class LongMemEvalBenchmarkTests(unittest.TestCase):
    def test_native_evidence_is_hidden_from_ranker_but_available_to_scorer(
        self,
    ) -> None:
        record = next(iter(iter_longmemeval(FIXTURE)))
        query, gold = retrieval_view(record)
        self.assertFalse(query.explicit_target_ids)
        self.assertNotIn(str(record.answer), query.text)
        ranking = BM25Ranker().rank(query)
        metrics = score_query(
            [item.candidate_id for item in ranking],
            gold,
            (1, 2),
        )
        self.assertEqual(metrics["at_k"]["2"]["evidence_recall"], 1.0)
        self.assertGreater(metrics["at_k"]["2"]["binary_ndcg"], 0.0)

    def test_native_candidate_ids_remain_unique(self) -> None:
        record = next(iter(iter_longmemeval(FIXTURE)))
        query, _ = retrieval_view(record)
        candidate_ids = [candidate.candidate_id for candidate in query.candidates]
        self.assertEqual(len(candidate_ids), len(set(candidate_ids)))

    def test_native_history_envelope_survives_question_date_anomaly(
        self,
    ) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))[0]
        raw["question_date"] = raw["haystack_dates"][0]
        anomalous = LongMemEvalRecord.from_dict(raw)
        query, _ = retrieval_view(anomalous)
        audit = native_timestamp_audit(anomalous)
        self.assertEqual(len(query.candidates), 2)
        self.assertGreater(
            audit["session_after_question_date"]
            + audit["session_equal_question_date"],
            0,
        )

    def test_negative_interval_excludes_zero_without_favoring_system(
        self,
    ) -> None:
        methods = {
            "baseline": {
                "per_query": {
                    "q1": {"at_k": {"10": {"evidence_recall": 1.0}}},
                    "q2": {"at_k": {"10": {"evidence_recall": 1.0}}},
                }
            },
            "intervention": {
                "per_query": {
                    "q1": {"at_k": {"10": {"evidence_recall": 0.0}}},
                    "q2": {"at_k": {"10": {"evidence_recall": 0.0}}},
                }
            },
        }
        result = _comparison(
            "baseline",
            "intervention",
            methods,
            top_k=10,
            seed=1729,
        )
        self.assertTrue(result["confidence_interval_excludes_zero"])
        self.assertFalse(
            result["confidence_interval_favors_intervention"]
        )
        self.assertFalse(result["retrieval_effect_passes"])


if __name__ == "__main__":
    unittest.main()
