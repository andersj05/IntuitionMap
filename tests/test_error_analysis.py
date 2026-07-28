from __future__ import annotations

import unittest
from pathlib import Path

from intuition_map_eval.baseline import (
    LexicalTemporalBaseline,
    LexicalTemporalConfig,
)
from intuition_map_eval.dataset import load_dataset
from intuition_map_eval.error_analysis import analyze_retrieval_errors

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ErrorAnalysisTests(unittest.TestCase):
    def test_error_rows_use_only_stable_taxonomy_codes(self) -> None:
        dataset = load_dataset(PROJECT_ROOT / "datasets" / "smoke")
        predictions = LexicalTemporalBaseline(
            LexicalTemporalConfig()
        ).rank(dataset)
        report = analyze_retrieval_errors(dataset, predictions, k=1)
        allowed = {
            "MISSED_EXPLICIT",
            "MISSED_ASSOCIATIVE",
            "GENERIC_HUB",
            "CONTEXT_COLLAPSE",
            "PROVENANCE_INVERSION",
            "DIRECTION_ERROR",
            "RELATION_ERROR",
            "CONTRADICTION_MISSED",
            "TEMPORAL_LEAKAGE",
            "DUPLICATE_INFLATION",
            "GRAPH_SATURATION",
            "OVERLY_SAFE",
        }
        self.assertTrue(report["screening_only"])
        self.assertGreater(report["summary"]["error_row_count"], 0)
        for row in report["rows"]:
            self.assertTrue(set(row["codes"]) <= allowed)
            self.assertTrue(row["adjudication_required"])


if __name__ == "__main__":
    unittest.main()
