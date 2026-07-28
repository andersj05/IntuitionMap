from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from intuition_map_eval.splits import (
    QueryObservation,
    rolling_origin_splits,
)
from intuition_map_eval.statistics import paired_query_bootstrap


class StatisticsAndSplitTests(unittest.TestCase):
    def test_paired_bootstrap_is_deterministic_and_query_paired(self) -> None:
        baseline = {"q1": 0.0, "q2": 0.5, "q3": 1.0}
        intervention = {"q1": 1.0, "q2": 1.0, "q3": 1.0}
        first = paired_query_bootstrap(
            baseline, intervention, resamples=200, seed=1729
        )
        second = paired_query_bootstrap(
            baseline, intervention, resamples=200, seed=1729
        )
        self.assertEqual(first, second)
        self.assertAlmostEqual(first.absolute_delta, 0.5)
        with self.assertRaisesRegex(ValueError, "query ids differ"):
            paired_query_bootstrap(
                baseline, {"q1": 1.0}, resamples=10
            )

    def test_rolling_splits_keep_same_query_rows_together(self) -> None:
        origin = datetime(2026, 1, 1, tzinfo=timezone.utc)
        observations = []
        for index in range(6):
            observation = QueryObservation(
                query_id=f"q{index}",
                captured_at=origin + timedelta(days=index),
            )
            observations.extend((observation, observation))
        splits = rolling_origin_splits(
            observations,
            initial_train_blocks=2,
            validation_blocks=1,
            test_blocks=1,
            step_blocks=1,
        )
        self.assertEqual(len(splits), 3)
        for split in splits:
            train = set(split.train_query_ids)
            validation = set(split.validation_query_ids)
            test = set(split.test_query_ids)
            self.assertFalse(train & validation)
            self.assertFalse(train & test)
            self.assertFalse(validation & test)
            self.assertEqual(len(split.definition_sha256), 64)

    def test_rolling_splits_never_split_one_capture_time_block(self) -> None:
        origin = datetime(2026, 1, 1, tzinfo=timezone.utc)
        observations = [
            QueryObservation("q1", origin),
            QueryObservation("q2", origin),
            QueryObservation("q3", origin + timedelta(days=1)),
            QueryObservation("q4", origin + timedelta(days=2)),
        ]
        split = rolling_origin_splits(
            observations,
            initial_train_blocks=1,
            validation_blocks=1,
            test_blocks=1,
        )[0]
        self.assertEqual(set(split.train_query_ids), {"q1", "q2"})
        self.assertLess(split.train_end, split.validation_end)

    def test_same_query_cannot_have_multiple_timestamps(self) -> None:
        origin = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError, "multiple timestamps"):
            rolling_origin_splits(
                [
                    QueryObservation("q1", origin),
                    QueryObservation("q1", origin + timedelta(days=1)),
                    QueryObservation("q2", origin + timedelta(days=2)),
                    QueryObservation("q3", origin + timedelta(days=3)),
                ],
                initial_train_blocks=1,
                validation_blocks=1,
                test_blocks=1,
            )


if __name__ == "__main__":
    unittest.main()
