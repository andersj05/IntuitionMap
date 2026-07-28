from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intuition_map_eval.dataset import load_dataset

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DatasetTests(unittest.TestCase):
    def test_smoke_dataset_is_valid_and_stable(self) -> None:
        dataset = load_dataset(PROJECT_ROOT / "datasets" / "smoke")
        self.assertEqual(len(dataset.thoughts), 10)
        self.assertEqual(len(dataset.judgments), 15)
        self.assertEqual(len(dataset.fingerprint), 64)
        self.assertFalse(dataset.manifest.annotation.exhaustive)

    def test_future_target_is_rejected_as_temporal_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": "0.1.0",
                        "name": "bad-time",
                        "description": "Fixture with a future target.",
                        "provenance": "test",
                        "contains_personal_data": False,
                        "annotation": {
                            "candidate_pool": "all_prior_thoughts",
                            "exhaustive": False,
                            "unlabeled_pairs_are": "unknown",
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "thoughts.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "id": "older",
                                "text": "Older thought",
                                "created_at": "2026-01-01T00:00:00Z",
                            }
                        ),
                        json.dumps(
                            {
                                "id": "newer",
                                "text": "Newer thought",
                                "created_at": "2026-01-02T00:00:00Z",
                            }
                        ),
                    ]
                ),
                encoding="utf-8",
            )
            (root / "judgments.jsonl").write_text(
                json.dumps(
                    {
                        "source_id": "older",
                        "target_id": "newer",
                        "verdict": "valid",
                        "relation_types": ["related"],
                        "strength": 0.5,
                        "rationale": "Invalid temporal direction.",
                        "annotator": "test",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "temporal leakage"):
                load_dataset(root)


if __name__ == "__main__":
    unittest.main()

