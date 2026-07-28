from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intuition_map_eval.baseline import (
    LexicalTemporalBaseline,
    LexicalTemporalConfig,
    Prediction,
)
from intuition_map_eval.dataset import load_dataset
from intuition_map_eval.metrics import compute_metrics
from intuition_map_eval.runner import run_experiment

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class EvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dataset = load_dataset(PROJECT_ROOT / "datasets" / "smoke")
        self.predictions = LexicalTemporalBaseline(
            LexicalTemporalConfig()
        ).rank(self.dataset)

    def test_rankings_only_include_prior_thoughts(self) -> None:
        thoughts_by_id = self.dataset.thoughts_by_id
        for prediction in self.predictions:
            source = thoughts_by_id[prediction.source_id]
            target = thoughts_by_id[prediction.target_id]
            self.assertLess(target.created_at, source.created_at)

    def test_metrics_distinguish_unknown_from_invalid(self) -> None:
        metrics = compute_metrics(self.dataset, self.predictions, [1, 3, 5])
        self.assertEqual(
            metrics["coverage"]["annotation_exhaustive"], False
        )
        self.assertIn(
            "known_invalid_predictions_per_judged_query",
            metrics["at_k"]["3"],
        )
        self.assertNotIn("precision", metrics["at_k"]["3"])
        self.assertGreaterEqual(metrics["mean_reciprocal_rank"], 0)
        self.assertLessEqual(metrics["mean_reciprocal_rank"], 1)
        self.assertIn(
            "judged_graded_ndcg_lower_bound",
            metrics["at_k"]["3"],
        )
        self.assertIn("relation_type", metrics["subgroups"])
        self.assertIn("time_distance", metrics["subgroups"])

    def test_duplicate_predictions_are_rejected(self) -> None:
        duplicate = (self.predictions[0], self.predictions[0])
        with self.assertRaisesRegex(ValueError, "duplicate prediction"):
            compute_metrics(self.dataset, duplicate, [1])

    def test_runner_writes_auditable_zero_cost_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_path, metrics = run_experiment(
                dataset_path=PROJECT_ROOT / "datasets" / "smoke",
                config_path=PROJECT_ROOT / "configs" / "lexical-baseline.json",
                output_root=temporary_directory,
            )
            self.assertTrue((run_path / "manifest.json").is_file())
            self.assertTrue((run_path / "predictions.jsonl").is_file())
            self.assertTrue((run_path / "error-analysis.json").is_file())
            usage = json.loads(
                (run_path / "usage.json").read_text(encoding="utf-8")
            )
            self.assertEqual(usage["paid_api_request_count"], 0)
            self.assertEqual(usage["estimated_cost_usd"], "0")
            self.assertEqual(
                metrics["runtime"]["paid_api_request_count"], 0
            )

    def test_empty_judgments_return_none_instead_of_fabricating_negatives(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for name in ("manifest.json", "thoughts.jsonl"):
                (root / name).write_text(
                    (
                        PROJECT_ROOT / "datasets" / "smoke" / name
                    ).read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
            (root / "judgments.jsonl").write_text("", encoding="utf-8")
            dataset = load_dataset(root)
            predictions = LexicalTemporalBaseline(
                LexicalTemporalConfig()
            ).rank(dataset)
            metrics = compute_metrics(dataset, predictions, [5])
            self.assertIsNone(metrics["mean_reciprocal_rank"])
            self.assertIsNone(
                metrics["at_k"]["5"]["relevant_macro_recall"]
            )
            self.assertIsNone(
                metrics["at_k"]["5"][
                    "known_invalid_predictions_per_judged_query"
                ]
            )
            self.assertEqual(metrics["per_query"], {})

    def test_invalid_exposure_has_an_exact_judged_query_denominator(
        self,
    ) -> None:
        predictions = (
            Prediction(
                source_id="t006",
                target_id="t004",
                rank=1,
                score=1.0,
                signals={},
            ),
        )
        metrics = compute_metrics(self.dataset, predictions, [1])
        self.assertAlmostEqual(
            metrics["at_k"]["1"][
                "known_invalid_predictions_per_judged_query"
            ],
            1 / 6,
        )
        self.assertEqual(
            metrics["at_k"]["1"]["invalid_rate_among_judged_predictions"],
            1.0,
        )

    def test_calibration_ready_fields_are_validated(self) -> None:
        invalid = (
            Prediction(
                source_id="t002",
                target_id="t001",
                rank=1,
                score=0.5,
                signals={},
                method="future-calibrator",
                confidence=1.5,
                abstained=False,
            ),
        )
        with self.assertRaisesRegex(ValueError, "confidence"):
            compute_metrics(self.dataset, invalid, [1])


if __name__ == "__main__":
    unittest.main()
