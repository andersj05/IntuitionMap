from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from intuition_map_eval.dataset import load_dataset
from intuition_map_eval.runner import load_experiment_config, run_experiment
from intuition_map_models.retrieval import (
    BM25Ranker,
    ExplicitLinkRanker,
    HashedEmbeddingRanker,
    MostRecentRanker,
    ReciprocalRankFusionRanker,
    RetrievalCandidate,
    RetrievalQuery,
    StableRandomRanker,
    TfIdfRanker,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.query = RetrievalQuery(
            query_id="q1",
            text="Where is the blue notebook?",
            candidates=(
                RetrievalCandidate(
                    candidate_id="old-red",
                    text="The red folder is on the shelf.",
                    order=0,
                ),
                RetrievalCandidate(
                    candidate_id="new-blue",
                    text="I placed the blue notebook in the desk.",
                    order=1,
                ),
            ),
            explicit_target_ids=("old-red",),
        )

    def test_transparent_rankers_are_deterministic(self) -> None:
        rankers = (
            StableRandomRanker(1729),
            MostRecentRanker(),
            TfIdfRanker(),
            BM25Ranker(),
            ExplicitLinkRanker(),
            HashedEmbeddingRanker(dimensions=64, seed=1729),
            ReciprocalRankFusionRanker(
                (
                    BM25Ranker(),
                    HashedEmbeddingRanker(dimensions=64, seed=1729),
                    MostRecentRanker(),
                )
            ),
        )
        for ranker in rankers:
            with self.subTest(ranker=ranker.name):
                self.assertEqual(
                    ranker.rank(self.query),
                    ranker.rank(self.query),
                )

    def test_lexical_methods_find_the_matching_candidate(self) -> None:
        for ranker in (
            TfIdfRanker(),
            BM25Ranker(),
            HashedEmbeddingRanker(dimensions=512, seed=1729),
        ):
            with self.subTest(ranker=ranker.name):
                self.assertEqual(
                    ranker.rank(self.query)[0].candidate_id,
                    "new-blue",
                )

    def test_recency_and_explicit_controls_measure_distinct_signals(self) -> None:
        self.assertEqual(
            MostRecentRanker().rank(self.query)[0].candidate_id,
            "new-blue",
        )
        self.assertEqual(
            ExplicitLinkRanker().rank(self.query)[0].candidate_id,
            "old-red",
        )

    def test_duplicate_candidate_ids_are_rejected(self) -> None:
        duplicate = RetrievalQuery(
            query_id="duplicate",
            text="query",
            candidates=(
                RetrievalCandidate("same", "one", 0),
                RetrievalCandidate("same", "two", 1),
            ),
        )
        with self.assertRaisesRegex(ValueError, "duplicate candidate"):
            BM25Ranker().rank(duplicate)

    def test_all_phase2_configs_run_offline_and_emit_calibration_status(
        self,
    ) -> None:
        dataset_path = PROJECT_ROOT / "datasets" / "smoke"
        config_paths = sorted(
            (PROJECT_ROOT / "configs" / "phase2").glob("*.json")
        )
        self.assertEqual(len(config_paths), 7)
        with tempfile.TemporaryDirectory() as temporary:
            for config_path in config_paths:
                with self.subTest(config=config_path.name):
                    config = load_experiment_config(config_path)
                    self.assertFalse(config.budget["allow_paid_api"])
                    self.assertEqual(config.budget["max_cost_usd"], 0)
                    run_path, metrics = run_experiment(
                        dataset_path=dataset_path,
                        config_path=config_path,
                        output_root=temporary,
                    )
                    first_row = (
                        run_path / "predictions.jsonl"
                    ).read_text(encoding="utf-8").splitlines()[0]
                    self.assertIn('"status":"uncalibrated"', first_row)
                    self.assertEqual(
                        metrics["runtime"]["paid_api_request_count"], 0
                    )

    def test_old_smoke_dataset_remains_compatible_with_optional_links(self) -> None:
        dataset = load_dataset(PROJECT_ROOT / "datasets" / "smoke")
        self.assertTrue(
            all(not thought.explicit_links for thought in dataset.thoughts)
        )


if __name__ == "__main__":
    unittest.main()
